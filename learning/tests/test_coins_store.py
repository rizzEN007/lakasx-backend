from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from learning.models import (
    CoinTransaction,
    Question,
    SchoolMembership,
    Student,
    StoreItem,
    StudentItem,
)
from learning.services.coins import award_coins

pytestmark = pytest.mark.django_db
Role = SchoolMembership.Role
Reason = CoinTransaction.Reason

START = "/api/practice/start/"
NEXT = "/api/practice/next-question/"
ANSWER = "/api/practice/answer/"
SHOP = "/api/store/shop/"
WALLET = "/api/store/wallet/"
INVENTORY = "/api/store/inventory/"
BUY = "/api/store/buy/"
EQUIP = "/api/store/equip/"
UNEQUIP = "/api/store/unequip/"
CATALOG = "/api/store-items/"


@pytest.fixture(autouse=True)
def _rules(settings):
    settings.PRACTICE_SESSION_LENGTH = 3
    settings.DAILY_GOAL_QUESTIONS = 99  # keeps the daily goal out of the way unless a test lowers it
    settings.COIN_STREAK_MILESTONES = [7, 30]
    settings.COIN_RULES = {
        "CORRECT_ANSWER": 2,
        "FIRST_TRY_BONUS": 1,
        "SESSION_COMPLETE": 10,
        "DAILY_GOAL": 10,
        "STREAK_MILESTONE": 50,
    }


@pytest.fixture
def kid(make_user, school_a, student_a):
    user = make_user("kid", school_a, Role.STUDENT)
    student_a.user = user
    student_a.grade = 4
    student_a.save()
    return user


@pytest.fixture
def other_kid(make_user, school_a):
    user = make_user("other_kid", school_a, Role.STUDENT)
    student = Student.objects.create(
        name="Chitra", email="chitra@example.com", school=school_a, grade=4, user=user
    )
    return user, student


@pytest.fixture
def hat(db):
    return StoreItem.objects.create(name="Red cap", slot="HAT", price=60, asset_key="hat_red_cap")


@pytest.fixture
def hat2(db):
    return StoreItem.objects.create(name="Blue cap", slot="HAT", price=80, asset_key="hat_blue_cap")


@pytest.fixture
def forest(db):
    return StoreItem.objects.create(name="Forest", slot="BACKGROUND", price=150, asset_key="bg_forest")


def fund(student, amount):
    Student.objects.filter(pk=student.pk).update(coin_balance=amount)
    student.refresh_from_db()


def make_questions(n):
    return [
        Question.objects.create(text=f"{i}+{i}?", answer=str(2 * i), grade=4)
        for i in range(1, n + 1)
    ]


def serve(client):
    res = client.post(NEXT)
    assert res.status_code == 200, res.json()
    return res.json()["question"]["id"]


def answer_right(client):
    qid = serve(client)
    correct = Question.objects.get(pk=qid).answer
    return client.post(ANSWER, {"answer_given": correct}, format="json").json()


def buy(client, item):
    return client.post(BUY, {"item_id": item.id}, format="json")


def equipped(student):
    return set(
        StudentItem.objects.filter(student=student, equipped=True).values_list("slot", "item_id")
    )


# ---- earning coins ------------------------------------------------------

def test_correct_first_try_earns_coins(client_for, kid, student_a):
    make_questions(5)
    client = client_for(kid)
    client.post(START)
    body = answer_right(client)
    assert body["coins_earned"] == 3  # 2 + 1 first-try bonus
    assert body["coin_balance"] == 3
    student_a.refresh_from_db()
    assert student_a.coin_balance == 3
    assert set(CoinTransaction.objects.values_list("reason", flat=True)) == {
        "CORRECT_ANSWER",
        "FIRST_TRY_BONUS",
    }


def test_wrong_answer_earns_no_coins(client_for, kid, student_a):
    make_questions(5)
    client = client_for(kid)
    client.post(START)
    serve(client)
    body = client.post(ANSWER, {"answer_given": "nope"}, format="json").json()
    assert body["coins_earned"] == 0
    assert not CoinTransaction.objects.exists()
    student_a.refresh_from_db()
    assert student_a.coin_balance == 0


def test_finishing_a_session_earns_a_bonus(client_for, kid, student_a):
    make_questions(5)
    client = client_for(kid)
    client.post(START)
    last = None
    for _ in range(3):
        last = answer_right(client)
    assert last["session_complete"] is True
    student_a.refresh_from_db()
    assert student_a.coin_balance == 3 * 3 + 10
    assert CoinTransaction.objects.filter(reason="SESSION_COMPLETE").count() == 1


def test_daily_goal_pays_once(client_for, kid, student_a, settings):
    settings.DAILY_GOAL_QUESTIONS = 2
    settings.PRACTICE_SESSION_LENGTH = 5
    make_questions(5)
    client = client_for(kid)
    client.post(START)
    for _ in range(3):
        answer_right(client)
    student_a.refresh_from_db()
    assert student_a.coin_balance == 3 + 3 + 10 + 3
    assert CoinTransaction.objects.filter(reason="DAILY_GOAL").count() == 1


def test_streak_milestone_pays_a_bonus(client_for, kid, student_a, settings):
    settings.DAILY_GOAL_QUESTIONS = 1
    settings.COIN_STREAK_MILESTONES = [2]
    Student.objects.filter(pk=student_a.pk).update(
        streak_count=1,
        longest_streak=1,
        last_goal_date=timezone.localdate() - timedelta(days=1),
    )
    make_questions(5)
    client = client_for(kid)
    client.post(START)
    body = answer_right(client)
    assert body["coins_earned"] == 3 + 10 + 50
    assert CoinTransaction.objects.filter(reason="STREAK_MILESTONE").count() == 1


def test_the_ledger_always_matches_the_balance(client_for, kid, student_a):
    make_questions(5)
    client = client_for(kid)
    client.post(START)
    answer_right(client)
    serve(client)
    client.post(ANSWER, {"answer_given": "wrong"}, format="json")
    answer_right(client)

    running = 0
    for entry in CoinTransaction.objects.order_by("id"):
        running += entry.amount
        assert entry.balance_after == running
    student_a.refresh_from_db()
    assert student_a.coin_balance == running


@pytest.mark.parametrize("amount", [0, -5])
def test_award_coins_rejects_non_positive_amounts(student_a, amount):
    with pytest.raises(ValueError):
        award_coins(student_a, amount, Reason.CORRECT_ANSWER)
    assert not CoinTransaction.objects.exists()


# ---- wallet and shop ----------------------------------------------------

def test_wallet_shows_balance_and_recent_activity(client_for, kid, student_a):
    award_coins(student_a, 7, Reason.CORRECT_ANSWER)
    body = client_for(kid).get(WALLET).json()
    assert body["balance"] == 7
    assert body["recent"][0]["amount"] == 7
    assert body["recent"][0]["reason"] == "CORRECT_ANSWER"


def test_shop_lists_only_active_items_with_flags(client_for, kid, student_a, hat, forest):
    StoreItem.objects.create(
        name="Hidden", slot="HAT", price=10, asset_key="hat_hidden", is_active=False
    )
    fund(student_a, 100)
    items = {i["name"]: i for i in client_for(kid).get(SHOP).json()}
    assert set(items) == {"Red cap", "Forest"}
    assert items["Red cap"]["can_afford"] is True
    assert items["Forest"]["can_afford"] is False
    assert items["Red cap"]["owned"] is False


# ---- buying -------------------------------------------------------------

def test_buying_charges_once_and_auto_equips(client_for, kid, student_a, hat):
    fund(student_a, 100)
    res = buy(client_for(kid), hat)
    assert res.status_code == 201
    assert res.json()["balance"] == 40
    student_a.refresh_from_db()
    assert student_a.coin_balance == 40
    owned = StudentItem.objects.get(student=student_a)
    assert owned.slot == "HAT" and owned.equipped is True
    purchase = CoinTransaction.objects.get(reason="PURCHASE")
    assert purchase.amount == -60
    assert purchase.balance_after == 40
    assert purchase.store_item_id == hat.id


def test_cannot_buy_without_enough_coins(client_for, kid, student_a, hat):
    fund(student_a, 59)
    res = buy(client_for(kid), hat)
    assert res.status_code == 409
    assert res.json()["code"] == "INSUFFICIENT_COINS"
    student_a.refresh_from_db()
    assert student_a.coin_balance == 59
    assert not StudentItem.objects.exists()
    assert not CoinTransaction.objects.filter(reason="PURCHASE").exists()


def test_cannot_buy_the_same_item_twice(client_for, kid, student_a, hat):
    fund(student_a, 200)
    client = client_for(kid)
    assert buy(client, hat).status_code == 201
    second = buy(client, hat)
    assert second.status_code == 409
    assert second.json()["code"] == "ALREADY_OWNED"
    student_a.refresh_from_db()
    assert student_a.coin_balance == 140
    assert StudentItem.objects.count() == 1


def test_unknown_and_inactive_items_cannot_be_bought(client_for, kid, student_a):
    fund(student_a, 500)
    retired = StoreItem.objects.create(
        name="Old", slot="HAT", price=10, asset_key="hat_old", is_active=False
    )
    client = client_for(kid)
    for item_id in (999999, retired.id):
        res = client.post(BUY, {"item_id": item_id}, format="json")
        assert res.status_code == 404
        assert res.json()["code"] == "ITEM_NOT_FOUND"
    student_a.refresh_from_db()
    assert student_a.coin_balance == 500


def test_item_id_is_required(client_for, kid):
    assert client_for(kid).post(BUY, {}, format="json").status_code == 400


# ---- equipping ----------------------------------------------------------

def test_a_second_item_in_the_same_slot_is_not_auto_equipped(
    client_for, kid, student_a, hat, hat2
):
    fund(student_a, 500)
    client = client_for(kid)
    buy(client, hat)
    second = buy(client, hat2)
    assert second.json()["equipped"] is False
    assert equipped(student_a) == {("HAT", hat.id)}


def test_items_in_different_slots_can_both_be_equipped(
    client_for, kid, student_a, hat, forest
):
    fund(student_a, 500)
    client = client_for(kid)
    buy(client, hat)
    buy(client, forest)
    assert equipped(student_a) == {("HAT", hat.id), ("BACKGROUND", forest.id)}


def test_equipping_swaps_within_a_slot_only(
    client_for, kid, student_a, hat, hat2, forest
):
    fund(student_a, 500)
    client = client_for(kid)
    for item in (hat, hat2, forest):
        buy(client, item)
    res = client.post(EQUIP, {"item_id": hat2.id}, format="json")
    assert res.status_code == 200
    assert equipped(student_a) == {("HAT", hat2.id), ("BACKGROUND", forest.id)}


def test_cannot_equip_an_item_you_do_not_own(client_for, kid, hat):
    res = client_for(kid).post(EQUIP, {"item_id": hat.id}, format="json")
    assert res.status_code == 409
    assert res.json()["code"] == "NOT_OWNED"


def test_unequip_clears_the_slot(client_for, kid, student_a, hat):
    fund(student_a, 100)
    client = client_for(kid)
    buy(client, hat)
    assert client.post(UNEQUIP, {"item_id": hat.id}, format="json").status_code == 200
    assert equipped(student_a) == set()
    assert client.get(INVENTORY).json()["equipped"] == {}


def test_inventory_reports_what_is_equipped(client_for, kid, student_a, hat):
    fund(student_a, 100)
    client = client_for(kid)
    buy(client, hat)
    body = client.get(INVENTORY).json()
    assert [i["item_id"] for i in body["items"]] == [hat.id]
    assert body["equipped"] == {"HAT": {"item_id": hat.id, "asset_key": "hat_red_cap"}}


# ---- isolation and access ----------------------------------------------

def test_inventories_and_wallets_are_per_student(
    client_for, kid, student_a, other_kid, hat
):
    other_user, other_student = other_kid
    fund(other_student, 100)
    assert buy(client_for(other_user), hat).status_code == 201
    assert client_for(kid).get(INVENTORY).json()["items"] == []
    student_a.refresh_from_db()
    assert student_a.coin_balance == 0
    assert StudentItem.objects.filter(student=other_student).count() == 1


@pytest.mark.parametrize("url", [SHOP, WALLET, INVENTORY])
def test_only_linked_students_can_use_the_store(client_for, teacher_a, outsider, url):
    assert client_for().get(url).status_code == 401
    assert client_for(teacher_a).get(url).status_code == 403
    assert client_for(outsider).get(url).status_code == 403


def test_students_cannot_set_their_own_balance(client_for, admin_a, student_a):
    client_for(admin_a).patch(
        f"/api/students/{student_a.id}/", {"coin_balance": 999}, format="json"
    )
    student_a.refresh_from_db()
    assert student_a.coin_balance == 0


# ---- database guarantees ------------------------------------------------

def test_database_allows_one_equipped_item_per_slot(student_a, hat, hat2):
    StudentItem.objects.create(student=student_a, item=hat, slot="HAT", equipped=True)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StudentItem.objects.create(
                student=student_a, item=hat2, slot="HAT", equipped=True
            )


def test_database_rejects_a_negative_balance(student_a):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Student.objects.filter(pk=student_a.pk).update(
                coin_balance=F("coin_balance") - 1
            )


# ---- catalog management -------------------------------------------------

def test_superuser_manages_the_catalog(client_for, superuser):
    client = client_for(superuser)
    created = client.post(
        CATALOG,
        {"name": "Cap", "slot": "HAT", "price": 50, "asset_key": "hat_cap"},
        format="json",
    )
    assert created.status_code == 201
    item_id = created.json()["id"]
    assert client.patch(f"{CATALOG}{item_id}/", {"price": 70}, format="json").status_code == 200
    assert StoreItem.objects.get(pk=item_id).price == 70
    assert client.delete(f"{CATALOG}{item_id}/").status_code == 405


def test_teacher_cannot_change_the_catalog(client_for, teacher_a, hat):
    client = client_for(teacher_a)
    assert client.post(
        CATALOG,
        {"name": "X", "slot": "HAT", "price": 5, "asset_key": "x"},
        format="json",
    ).status_code == 403
    assert client.patch(f"{CATALOG}{hat.id}/", {"price": 1}, format="json").status_code == 403
    hat.refresh_from_db()
    assert hat.price == 60


def test_members_see_only_active_catalog_items(client_for, teacher_a, hat):
    StoreItem.objects.create(
        name="Retired", slot="HAT", price=10, asset_key="hat_retired", is_active=False
    )
    res = client_for(teacher_a).get(CATALOG)
    data = res.json()
    rows = data["results"] if isinstance(data, dict) else data
    assert [r["name"] for r in rows] == ["Red cap"]


def test_catalog_price_must_be_positive(client_for, superuser):
    res = client_for(superuser).post(
        CATALOG,
        {"name": "Free", "slot": "HAT", "price": 0, "asset_key": "hat_free"},
        format="json",
    )
    assert res.status_code == 400