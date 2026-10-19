import math
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..models import LoginAttempt


def normalize(identifier):
    if not isinstance(identifier, str):
        return ""
    return identifier.strip().lower()[:150]


def seconds_locked(identifier):
    """Seconds left on the lock, or 0 if the username isn't locked."""
    key = normalize(identifier)
    if not key:
        return 0
    record = LoginAttempt.objects.filter(identifier=key).first()
    if record is None or record.locked_until is None:
        return 0
    remaining = (record.locked_until - timezone.now()).total_seconds()
    return max(0, math.ceil(remaining))


def register_failure(identifier):
    key = normalize(identifier)
    if not key:
        return
    now = timezone.now()
    window = timedelta(minutes=settings.LOGIN_FAILURE_WINDOW_MINUTES)

    with transaction.atomic():
        record, _ = LoginAttempt.objects.select_for_update().get_or_create(
            identifier=key
        )
        lock_expired = record.locked_until is not None and record.locked_until <= now
        if lock_expired or now - record.window_started_at > window:
            record.failed_count = 0
            record.locked_until = None
            record.window_started_at = now

        record.failed_count += 1
        if record.failed_count >= settings.LOGIN_MAX_FAILURES:
            record.locked_until = now + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
        record.save()


def clear_failures(identifier):
    key = normalize(identifier)
    if key:
        LoginAttempt.objects.filter(identifier=key).delete()