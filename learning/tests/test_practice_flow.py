from datetime import timedelta

import pytest
from django.utils import timezone

from learning.models import (
    PracticeSession,
    Question,
    QuestionAttempt,
    SchoolMembership,
    Student,
    XPEvent,
)

pytestmark = pytest.mark.django_db
Role = SchoolMembership.Role

START = "/api/practice/start/"
NEXT = "/api/practice/next-question/"
ANSWER = "/api/practice/answer/"
END = "/api/practice/end/"


@pytest.fixture(autouse=True)
def _practice_settings(settings):
    settings.PRACTICE_SESSION_LENGTH = 3
    settings.PRACTICE_SESSION_IDLE_MINUTES = 30
    settings.XP_RULES = {
        "CORRECT_ANSWER": 10,
        "FIRST_TRY_BONUS": 5,
        "SESSION_COMPLETE": 20,
    }


@pytest.fixture
def kid(make_user, school_a, student_a):
    user = make_user("kid", school_a, Role.STUDENT)
    student_a.user = user
    student_a.grade = 4
    student_a.save()
    return user


def make_questions(grade, count, start=1):
    return [
        Question.objects.create(text=f"{i}+{i}?", answer=str(i + i), grade=grade)
        for i in range(start, start + count)
    ]


def serve(client):
    res = client.post(NEXT)
    assert res.status_code == 200, res.json()
    return res.json()["question"]["id"]


def answer(client, text):
    return client.post(ANSWER, {"answer_given": text}, format="json")


def right_answer(question_id):
    return Question.objects.get(pk=question_id).answer


def age(session_id, minutes=31):
    PracticeSession.objects.filter(pk=session_id).update(
        last_activity_at=timezone.now() - timedelta(minutes=minutes)
    )


# ---- who can practice ---------------------------------------------------

def test_unauthenticated_gets_401(client_for):
    assert client_for().post(START).status_code == 401


def test_staff_cannot_practice(client_for, teacher_a):
    assert client_for(teacher_a).post(START).status_code == 403


def test_unlinked_student_login_cannot_practice(client_for, make_user, school_a):
    login = make_user("unlinked", school_a, Role.STUDENT)
    assert client_for(login).post(START).status_code == 403


# ---- starting -----------------------------------------------------------

def test_start_requires_a_grade(client_for, kid, student_a):
    Student.objects.filter(pk=student_a.pk).update(grade=None)
    make_questions(4, 3)
    res = client_for(kid).post(START)
    assert res.status_code == 409
    assert res.json()["code"] == "NO_GRADE"


def test_start_requires_questions_for_the_grade(client_for, kid):
    make_questions(5, 3)  # a different grade
    res = client_for(kid).post(START)
    assert res.status_code == 409
    assert res.json()["code"] == "NO_QUESTIONS"


def test_start_is_idempotent_while_a_session_is_open(client_for, kid):
    make_questions(4, 5)
    client = client_for(kid)
    first = client.post(START)
    second = client.post(START)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["session_id"] == second.json()["session_id"]
    assert PracticeSession.objects.filter(ended_at__isnull=True).count() == 1


# ---- serving questions --------------------------------------------------

def test_served_question_never_includes_the_answer(client_for, kid):
    make_questions(4, 5)
    client = client_for(kid)
    client.post(START)
    body = client.post(NEXT).json()
    assert set(body["question"]) == {"id", "text"}
    assert body["question_number"] == 1


def test_next_question_is_stable_until_answered(client_for, kid):
    make_questions(4, 5)
    client = client_for(kid)
    client.post(START)
    assert serve(client) == serve(client)


def test_only_valid_questions_for_the_students_grade_are_served(client_for, kid):
    good = make_questions(4, 3)
    make_questions(5, 3, start=10)  # wrong grade
    Question.objects.create(text="no answer", answer=None, grade=4)
    Question.objects.create(text="blank", answer="", grade=4)
    client = client_for(kid)
    client.post(START)
    served = []
    for _ in range(3):
        qid = serve(client)
        served.append(qid)
        answer(client, right_answer(qid))
    assert set(served) == {q.id for q in good}


# ---- answering and XP ---------------------------------------------------

def test_correct_first_try_earns_xp_and_bonus(client_for, kid, student_a):
    make_questions(4, 5)
    client = client_for(kid)
    client.post(START)
    qid = serve(client)
    res = answer(client, right_answer(qid))
    body = res.json()
    assert res.status_code == 200
    assert body["is_correct"] is True
    assert body["xp_earned"] == 15
    assert body["total_xp"] == 15
    student_a.refresh_from_db()
    assert student_a.total_xp == 15
    assert set(XPEvent.objects.values_list("reason", flat=True)) == {
        "CORRECT_ANSWER",
        "FIRST_TRY_BONUS",
    }
    attempt = QuestionAttempt.objects.get()
    assert attempt.is_first_try and attempt.is_correct


def test_wrong_answer_earns_nothing_and_reveals_the_answer(client_for, kid, student_a):
    make_questions(4, 5)
    client = client_for(kid)
    client.post(START)
    qid = serve(client)
    body = answer(client, "definitely wrong").json()
    assert body["is_correct"] is False
    assert body["xp_earned"] == 0
    assert body["correct_answer"] == right_answer(qid)
    student_a.refresh_from_db()
    assert student_a.total_xp == 0
    assert QuestionAttempt.objects.get().is_correct is False


def test_answer_needs_a_served_question(client_for, kid):
    make_questions(4, 5)
    client = client_for(kid)
    client.post(START)
    res = answer(client, "4")
    assert res.status_code == 409
    assert res.json()["code"] == "NO_QUESTION_SERVED"


def test_a_question_cannot_be_answered_twice(client_for, kid, student_a):
    make_questions(4, 5)
    client = client_for(kid)
    client.post(START)
    qid = serve(client)
    assert answer(client, right_answer(qid)).status_code == 200
    assert answer(client, right_answer(qid)).status_code == 409
    assert QuestionAttempt.objects.count() == 1
    student_a.refresh_from_db()
    assert student_a.total_xp == 15


def test_blank_answer_is_rejected(client_for, kid):
    make_questions(4, 5)
    client = client_for(kid)
    client.post(START)
    serve(client)
    assert answer(client, "   ").status_code == 400


# ---- finishing a session ------------------------------------------------

def test_session_completes_after_the_configured_length(client_for, kid, student_a):
    make_questions(4, 5)
    client = client_for(kid)
    client.post(START)
    last = None
    for _ in range(3):
        qid = serve(client)
        last = answer(client, right_answer(qid)).json()
    assert last["session_complete"] is True
    assert last["answered"] == 3
    assert last["xp_earned"] == 15 + 20
    student_a.refresh_from_db()
    assert student_a.total_xp == 3 * 15 + 20
    assert XPEvent.objects.filter(reason="SESSION_COMPLETE").count() == 1
    assert PracticeSession.objects.get().ended_at is not None
    res = client.post(NEXT)
    assert res.status_code == 409
    assert res.json()["code"] == "NO_ACTIVE_SESSION"


def test_ending_early_gives_no_completion_bonus(client_for, kid, student_a):
    make_questions(4, 5)
    client = client_for(kid)
    client.post(START)
    qid = serve(client)
    answer(client, right_answer(qid))
    res = client.post(END)
    assert res.status_code == 200
    assert res.json()["answered"] == 1
    assert res.json()["completed"] is False
    student_a.refresh_from_db()
    assert student_a.total_xp == 15
    assert client.post(NEXT).status_code == 409


def test_a_new_session_can_start_after_one_ends(client_for, kid):
    make_questions(4, 5)
    client = client_for(kid)
    first = client.post(START).json()["session_id"]
    client.post(END)
    second = client.post(START)
    assert second.status_code == 201
    assert second.json()["session_id"] != first


# ---- idle sessions ------------------------------------------------------

def test_idle_session_is_closed_when_a_new_one_starts(client_for, kid):
    make_questions(4, 5)
    client = client_for(kid)
    old = client.post(START).json()["session_id"]
    age(old)
    res = client.post(START)
    assert res.status_code == 201
    assert res.json()["session_id"] != old
    assert PracticeSession.objects.get(pk=old).ended_at is not None


def test_idle_session_cannot_be_answered(client_for, kid):
    make_questions(4, 5)
    client = client_for(kid)
    session_id = client.post(START).json()["session_id"]
    serve(client)
    age(session_id)
    res = answer(client, "4")
    assert res.status_code == 409
    assert res.json()["code"] == "NO_ACTIVE_SESSION"
    assert QuestionAttempt.objects.count() == 0


# ---- repeats and exhaustion --------------------------------------------

def test_missed_questions_come_back_and_are_not_first_try(client_for, kid):
    make_questions(4, 3)  # exactly one session's worth
    client = client_for(kid)
    client.post(START)
    for _ in range(3):
        serve(client)
        answer(client, "wrong")  # session 1: all wrong, completes
    client.post(START)
    qid = serve(client)  # nothing unseen is left, so a missed one returns
    body = answer(client, right_answer(qid)).json()
    assert body["is_correct"] is True
    assert body["xp_earned"] == 10  # correct, but no first-try bonus
    last_attempt = QuestionAttempt.objects.filter(question_id=qid).order_by("id").last()
    assert last_attempt.is_first_try is False


def test_session_ends_when_the_question_bank_is_exhausted(client_for, kid):
    make_questions(4, 1)
    client = client_for(kid)
    client.post(START)
    qid = serve(client)
    answer(client, right_answer(qid))
    res = client.post(NEXT)
    assert res.status_code == 409
    assert res.json()["code"] == "QUESTIONS_EXHAUSTED"
    assert PracticeSession.objects.get().ended_at is not None


# ---- results and the generic endpoint ----------------------------------

def test_student_reads_own_session_results(client_for, kid):
    make_questions(4, 5)
    client = client_for(kid)
    session_id = client.post(START).json()["session_id"]
    answer(client, "x")  # rejected: nothing served yet
    qid = serve(client)
    answer(client, right_answer(qid))
    body = client.get(f"/api/practice-sessions/{session_id}/results/").json()
    assert body["answered"] == 1 and body["correct"] == 1
    assert body["accuracy_percent"] == 100
    assert body["xp_earned"] == 15
    assert body["is_open"] is True


def test_student_cannot_read_a_classmates_results(client_for, kid, school_a):
    classmate = Student.objects.create(
        name="Chitra", email="chitra@example.com", school=school_a, grade=4
    )
    other = PracticeSession.objects.create(student=classmate)
    res = client_for(kid).get(f"/api/practice-sessions/{other.id}/results/")
    assert res.status_code == 404


def test_staff_read_results_only_in_their_school(client_for, teacher_a, teacher_b, student_a):
    session = PracticeSession.objects.create(student=student_a)
    url = f"/api/practice-sessions/{session.id}/results/"
    assert client_for(teacher_a).get(url).status_code == 200
    assert client_for(teacher_b).get(url).status_code == 404


def test_staff_cannot_create_sessions_through_the_generic_endpoint(
    client_for, teacher_a, student_a
):
    res = client_for(teacher_a).post(
        "/api/practice-sessions/", {"student": student_a.id}, format="json"
    )
    assert res.status_code == 405