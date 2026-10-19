from django.db import transaction

from ..models import CoinTransaction, Student, StoreItem, StudentItem
from .coins import record_transaction


class StoreError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _lock(student):
    # Locking the student serializes all of their purchases and equips,
    # so double taps can't overspend or double-buy.
    return Student.objects.select_for_update().get(pk=student.pk)


def _owned(locked, item_id):
    owned = (
        StudentItem.objects.select_related("item")
        .filter(student=locked, item_id=item_id)
        .first()
    )
    if owned is None:
        raise StoreError("NOT_OWNED", "You don't own that item.")
    return owned


def entry(owned):
    return {
        "item_id": owned.item_id,
        "name": owned.item.name,
        "slot": owned.slot,
        "asset_key": owned.item.asset_key,
        "equipped": owned.equipped,
    }


def buy_item(student, item_id):
    with transaction.atomic():
        locked = _lock(student)
        item = StoreItem.objects.filter(pk=item_id, is_active=True).first()
        if item is None:
            raise StoreError("ITEM_NOT_FOUND", "That item is not available.")
        if StudentItem.objects.filter(student=locked, item=item).exists():
            raise StoreError("ALREADY_OWNED", "You already own this item.")
        if locked.coin_balance < item.price:
            raise StoreError(
                "INSUFFICIENT_COINS",
                f"You need {item.price - locked.coin_balance} more coins.",
            )

        record_transaction(
            locked, -item.price, CoinTransaction.Reason.PURCHASE, store_item=item
        )
        slot_is_empty = not StudentItem.objects.filter(
            student=locked, slot=item.slot, equipped=True
        ).exists()
        owned = StudentItem.objects.create(
            student=locked, item=item, slot=item.slot, equipped=slot_is_empty
        )
    student.refresh_from_db(fields=["coin_balance"])
    owned.item = item
    return owned


def equip_item(student, item_id):
    with transaction.atomic():
        locked = _lock(student)
        owned = _owned(locked, item_id)
        StudentItem.objects.filter(
            student=locked, slot=owned.slot, equipped=True
        ).exclude(pk=owned.pk).update(equipped=False)
        if not owned.equipped:
            owned.equipped = True
            owned.save(update_fields=["equipped"])
    return owned


def unequip_item(student, item_id):
    with transaction.atomic():
        locked = _lock(student)
        owned = _owned(locked, item_id)
        if owned.equipped:
            owned.equipped = False
            owned.save(update_fields=["equipped"])
    return owned


def wallet(student):
    recent = student.coin_transactions.select_related("store_item").order_by(
        "-created_at", "-id"
    )[:20]
    return {
        "balance": student.coin_balance,
        "recent": [
            {
                "amount": t.amount,
                "reason": t.reason,
                "balance_after": t.balance_after,
                "item": t.store_item.name if t.store_item else None,
                "created_at": t.created_at,
            }
            for t in recent
        ],
    }


def shop(student):
    owned = {o.item_id: o for o in student.owned_items.all()}
    items = StoreItem.objects.filter(is_active=True).order_by("slot", "price", "id")
    return [
        {
            "id": item.pk,
            "name": item.name,
            "slot": item.slot,
            "price": item.price,
            "asset_key": item.asset_key,
            "owned": item.pk in owned,
            "equipped": bool(item.pk in owned and owned[item.pk].equipped),
            "can_afford": student.coin_balance >= item.price,
        }
        for item in items
    ]


def inventory(student):
    owned = student.owned_items.select_related("item").order_by("slot", "item__name")
    return {
        "items": [entry(o) for o in owned],
        "equipped": {
            o.slot: {"item_id": o.item_id, "asset_key": o.item.asset_key}
            for o in owned
            if o.equipped
        },
    }