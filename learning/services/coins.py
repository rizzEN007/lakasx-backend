from django.db import transaction

from ..models import CoinTransaction, Student


class InsufficientCoins(Exception):
    pass


def record_transaction(
    locked_student, amount, reason, practice_session=None, store_item=None
):
    """Apply a signed amount to a student who is already locked (select_for_update)."""
    new_balance = locked_student.coin_balance + amount
    if new_balance < 0:
        raise InsufficientCoins("Not enough coins.")
    locked_student.coin_balance = new_balance
    locked_student.save(update_fields=["coin_balance"])
    return CoinTransaction.objects.create(
        student=locked_student,
        amount=amount,
        balance_after=new_balance,
        reason=reason,
        practice_session=practice_session,
        store_item=store_item,
    )


def award_coins(student, amount, reason, practice_session=None):
    if amount <= 0:
        raise ValueError("Coin amount must be positive.")
    with transaction.atomic():
        locked = Student.objects.select_for_update().get(pk=student.pk)
        entry = record_transaction(
            locked, amount, reason, practice_session=practice_session
        )
    student.refresh_from_db(fields=["coin_balance"])
    return entry