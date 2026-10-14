from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from ..models import DailyActivity, PracticeSession, QuestionAttempt
from .streaks import streak_status
from .xp import xp_progress


def child_summary(student, relationship, today=None):
    xp = xp_progress(student.total_xp)
    return {
        "student_id": student.pk,
        "name": student.name,
        "grade": student.grade,
        "relationship": relationship,
        "total_xp": student.total_xp,
        "level": xp["level"],
        "xp_to_next_level": xp["xp_to_next_level"],
        "streak": streak_status(student, today=today),
    }


def weekly_summary(student, today=None):
    """The last 7 days (including today) for one student, in local time."""
    today = today or timezone.localdate()
    start = today - timedelta(days=6)
    window_start = timezone.make_aware(datetime.combine(start, time.min))
    window_end = timezone.make_aware(
        datetime.combine(today + timedelta(days=1), time.min)
    )

    records = {
        a.date: a
        for a in DailyActivity.objects.filter(
            student=student, date__range=(start, today)
        )
    }
    days = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        record = records.get(day)
        days.append(
            {
                "date": day,
                "questions_answered": record.questions_answered if record else 0,
                "xp_earned": record.xp_earned if record else 0,
                "goal_met": bool(record and record.goal_met),
            }
        )

    attempts = QuestionAttempt.objects.filter(
        practice_session__student=student,
        attempted_at__gte=window_start,
        attempted_at__lt=window_end,
    )
    totals = attempts.aggregate(
        answered=Count("id"), correct=Count("id", filter=Q(is_correct=True))
    )
    answered, correct = totals["answered"], totals["correct"]

    rows = attempts.values("question__topic__name").annotate(
        answered=Count("id"), correct=Count("id", filter=Q(is_correct=True))
    )
    topics = sorted(
        (
            {
                "topic": row["question__topic__name"] or "Uncategorized",
                "answered": row["answered"],
                "correct": row["correct"],
                "accuracy_percent": round(row["correct"] / row["answered"] * 100, 1),
            }
            for row in rows
        ),
        key=lambda t: (t["accuracy_percent"], t["topic"]),  # weakest first
    )

    sessions = PracticeSession.objects.filter(
        student=student, started_at__gte=window_start, started_at__lt=window_end
    ).count()

    xp = xp_progress(student.total_xp)
    return {
        "student": {"id": student.pk, "name": student.name, "grade": student.grade},
        "period": {"start": start, "end": today},
        "totals": {
            "sessions": sessions,
            "active_days": sum(1 for d in days if d["questions_answered"]),
            "questions_answered": answered,
            "correct": correct,
            "accuracy_percent": round(correct / answered * 100, 1) if answered else 0,
            "xp_earned": sum(d["xp_earned"] for d in days),
        },
        "days": days,
        "topics": topics,
        "streak": streak_status(student, today=today),
        "total_xp": student.total_xp,
        "level": xp["level"],
    }