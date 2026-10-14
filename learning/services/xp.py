from django.conf import settings
from django.db import transaction
from django.db.models import F

from ..models import Student, XPEvent


def xp_progress(total_xp):
    thresholds = settings.XP_LEVEL_THRESHOLDS
    level = sum(1 for t in thresholds if total_xp >= t)
    next_threshold = thresholds[level] if level < len(thresholds) else None
    return {
        "level": level,
        "xp_to_next_level": None if next_threshold is None else next_threshold - total_xp,
    }


def award_xp(student, amount, reason, practice_session=None):
    """Log an XP award and update the student's cached total atomically."""
    if amount <= 0:
        raise ValueError("XP amount must be positive.")

    with transaction.atomic():
        event = XPEvent.objects.create(
            student=student,
            amount=amount,
            reason=reason,
            practice_session=practice_session,
        )
        Student.objects.filter(pk=student.pk).update(
            total_xp=F("total_xp") + amount
        )

    student.refresh_from_db(fields=["total_xp"])
    return event