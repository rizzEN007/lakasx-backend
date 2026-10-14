from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..models import DailyActivity, Student


def _resolve(today):
    return today or timezone.localdate()


def effective_streak(student, today=None):
    """The streak as of today. A stored count expires after a missed day."""
    today = _resolve(today)
    last = student.last_goal_date
    if last is None or last < today - timedelta(days=1):
        return 0
    return student.streak_count


def streak_status(student, today=None):
    today = _resolve(today)
    activity = DailyActivity.objects.filter(student=student, date=today).first()
    goal_met_today = bool(activity and activity.goal_met)
    current = effective_streak(student, today)
    return {
        "current": current,
        "longest": student.longest_streak,
        "daily_goal": settings.DAILY_GOAL_QUESTIONS,
        "questions_today": activity.questions_answered if activity else 0,
        "goal_met_today": goal_met_today,
        "at_risk": current > 0 and not goal_met_today,
    }


def record_activity(student, xp_earned=0, today=None):
    """Count one answered question toward today's goal.

    Returns True if this answer is the one that met the goal and extended the streak.
    """
    today = _resolve(today)
    extended = False

    with transaction.atomic():
        # Lock the student so concurrent answers can't double-extend a streak.
        locked = Student.objects.select_for_update().get(pk=student.pk)
        activity, _ = DailyActivity.objects.get_or_create(student=locked, date=today)
        activity.questions_answered += 1
        activity.xp_earned += xp_earned

        if (
            not activity.goal_met
            and activity.questions_answered >= settings.DAILY_GOAL_QUESTIONS
        ):
            activity.goal_met = True
            continues = locked.last_goal_date == today - timedelta(days=1)
            locked.streak_count = locked.streak_count + 1 if continues else 1
            locked.longest_streak = max(locked.longest_streak, locked.streak_count)
            locked.last_goal_date = today
            locked.save(
                update_fields=["streak_count", "longest_streak", "last_goal_date"]
            )
            extended = True

        activity.save()

    student.refresh_from_db(
        fields=["streak_count", "longest_streak", "last_goal_date"]
    )
    return extended