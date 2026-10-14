import random
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Sum
from django.utils import timezone

from ..models import PracticeSession, Question, QuestionAttempt, XPEvent
from .xp import award_xp, xp_progress


class PracticeError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def is_correct_answer(question, answer_given):
    expected = question.answer
    return (
        expected is not None
        and expected.strip().casefold() == answer_given.strip().casefold()
    )


def _award(student, reason, session):
    amount = settings.XP_RULES[reason.value]
    award_xp(student, amount, reason, practice_session=session)
    return amount


def _open_sessions(student):
    return PracticeSession.objects.filter(student=student, ended_at__isnull=True)


def _close_stale_sessions(student):
    cutoff = timezone.now() - timedelta(minutes=settings.PRACTICE_SESSION_IDLE_MINUTES)
    _open_sessions(student).filter(last_activity_at__lt=cutoff).update(
        ended_at=F("last_activity_at"),
        current_question=None,
        served_at=None,
    )


def _lock_open_session(student):
    session = _open_sessions(student).select_for_update().first()
    if session is None:
        raise PracticeError("NO_ACTIVE_SESSION", "Start a new practice session first.")
    return session


def _servable_questions(grade):
    return (
        Question.objects.filter(grade=grade)
        .exclude(answer__isnull=True)
        .exclude(answer="")
    )


def _pick_question(student, session):
    in_session = session.question_attempts.values_list("question_id", flat=True)
    candidates = _servable_questions(student.grade).exclude(pk__in=in_session)

    # Questions this student has never answered come first.
    seen = QuestionAttempt.objects.filter(
        practice_session__student=student
    ).values_list("question_id", flat=True)
    unseen_ids = list(candidates.exclude(pk__in=seen).values_list("pk", flat=True))
    if unseen_ids:
        return Question.objects.get(pk=random.choice(unseen_ids))

    # Then questions they have answered wrong at least once.
    missed_ids = list(
        candidates.filter(
            attempts__practice_session__student=student,
            attempts__is_correct=False,
        ).values_list("pk", flat=True).distinct()
    )
    if missed_ids:
        return Question.objects.get(pk=random.choice(missed_ids))

    return None


def start_session(student):
    if student.grade is None:
        raise PracticeError("NO_GRADE", "Your teacher needs to set your class first.")

    _close_stale_sessions(student)
    session = _open_sessions(student).first()
    if session is not None:
        return session, False

    if not _servable_questions(student.grade).exists():
        raise PracticeError("NO_QUESTIONS", "There are no questions for your class yet.")

    try:
        with transaction.atomic():
            session = PracticeSession.objects.create(student=student)
    except IntegrityError:
        # Two requests raced; the database allows one open session, so reuse it.
        session = _open_sessions(student).first()
        if session is None:
            raise
        return session, False
    return session, True


def next_question(student):
    _close_stale_sessions(student)
    problem = None

    with transaction.atomic():
        session = _lock_open_session(student)

        if session.current_question_id:
            return session, session.current_question  # same question until answered

        question = None
        if session.question_attempts.count() >= settings.PRACTICE_SESSION_LENGTH:
            problem = ("SESSION_COMPLETE", "This session is already complete.")
        else:
            question = _pick_question(student, session)
            if question is None:
                problem = (
                    "QUESTIONS_EXHAUSTED",
                    "You've answered every question available for your class for now.",
                )

        now = timezone.now()
        if problem:
            session.ended_at = now
            session.save(update_fields=["ended_at"])
        else:
            session.current_question = question
            session.served_at = now
            session.last_activity_at = now
            session.save(update_fields=["current_question", "served_at", "last_activity_at"])

    if problem:
        raise PracticeError(*problem)
    return session, question


def submit_answer(student, answer_given):
    _close_stale_sessions(student)

    with transaction.atomic():
        session = _lock_open_session(student)
        question = session.current_question
        if question is None:
            raise PracticeError("NO_QUESTION_SERVED", "Ask for a question before answering.")

        now = timezone.now()
        is_correct = is_correct_answer(question, answer_given)
        first_try = not QuestionAttempt.objects.filter(
            practice_session__student=student, question=question
        ).exists()
        time_taken = max(0, int((now - (session.served_at or now)).total_seconds()))

        QuestionAttempt.objects.create(
            question=question,
            practice_session=session,
            answer_given=answer_given,
            is_correct=is_correct,
            is_first_try=first_try,
            time_taken_seconds=time_taken,
        )

        xp_earned = 0
        if is_correct:
            xp_earned += _award(student, XPEvent.Reason.CORRECT_ANSWER, session)
            if first_try:
                xp_earned += _award(student, XPEvent.Reason.FIRST_TRY_BONUS, session)

        answered = session.question_attempts.count()
        complete = answered >= settings.PRACTICE_SESSION_LENGTH
        if complete:
            xp_earned += _award(student, XPEvent.Reason.SESSION_COMPLETE, session)
            session.ended_at = now

        session.current_question = None
        session.served_at = None
        session.last_activity_at = now
        session.save(
            update_fields=["current_question", "served_at", "last_activity_at", "ended_at"]
        )

    student.refresh_from_db(fields=["total_xp"])
    progress = xp_progress(student.total_xp)
    return {
        "is_correct": is_correct,
        "correct_answer": question.answer,
        "time_taken_seconds": time_taken,
        "xp_earned": xp_earned,
        "total_xp": student.total_xp,
        "level": progress["level"],
        "xp_to_next_level": progress["xp_to_next_level"],
        "answered": answered,
        "session_length": settings.PRACTICE_SESSION_LENGTH,
        "session_complete": complete,
    }


def end_session(student):
    _close_stale_sessions(student)
    with transaction.atomic():
        session = _lock_open_session(student)
        session.ended_at = timezone.now()
        session.current_question = None
        session.served_at = None
        session.save(update_fields=["ended_at", "current_question", "served_at"])
    return session


def session_results(session):
    attempts = list(session.question_attempts.all())
    answered = len(attempts)
    correct = sum(1 for a in attempts if a.is_correct)
    xp_earned = session.xp_events.aggregate(total=Sum("amount"))["total"] or 0
    return {
        "session_id": session.pk,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "is_open": session.ended_at is None,
        "answered": answered,
        "correct": correct,
        "accuracy_percent": round(correct / answered * 100, 1) if answered else 0,
        "xp_earned": xp_earned,
        "completed": answered >= settings.PRACTICE_SESSION_LENGTH,
    }