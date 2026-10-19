from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from learning.models import LoginAttempt

pytestmark = pytest.mark.django_db
User = get_user_model()

LOGIN = "/api/auth/login/"
REFRESH = "/api/auth/token/refresh/"
LOGOUT = "/api/auth/logout/"
GOOD = "pass12345!"


@pytest.fixture(autouse=True)
def _lock_rules(settings):
    settings.LOGIN_MAX_FAILURES = 3
    settings.LOGIN_LOCK_MINUTES = 15
    settings.LOGIN_FAILURE_WINDOW_MINUTES = 15


def login(client, username, password):
    return client.post(LOGIN, {"username": username, "password": password}, format="json")


def fail(client, username, times):
    return [login(client, username, "wrong").status_code for _ in range(times)]


def tokens(client, username="alice"):
    return login(client, username, GOOD).json()


# ---- account lock -------------------------------------------------------

def test_repeated_failures_lock_the_account(client_for, make_user):
    make_user("alice")
    client = client_for()
    assert fail(client, "alice", 3) == [401, 401, 401]
    res = login(client, "alice", GOOD)  # even the right password is refused
    assert res.status_code == 429
    assert int(res["Retry-After"]) > 0


def test_attempts_while_locked_do_not_extend_the_lock(client_for, make_user):
    make_user("alice")
    client = client_for()
    fail(client, "alice", 3)
    first = LoginAttempt.objects.get(identifier="alice").locked_until
    fail(client, "alice", 3)
    assert LoginAttempt.objects.get(identifier="alice").locked_until == first


def test_the_lock_expires(client_for, make_user):
    make_user("alice")
    client = client_for()
    fail(client, "alice", 3)
    LoginAttempt.objects.filter(identifier="alice").update(
        locked_until=timezone.now() - timedelta(seconds=1)
    )
    assert login(client, "alice", GOOD).status_code == 200
    assert not LoginAttempt.objects.filter(identifier="alice").exists()


def test_a_successful_login_resets_the_counter(client_for, make_user):
    make_user("alice")
    client = client_for()
    fail(client, "alice", 2)
    assert login(client, "alice", GOOD).status_code == 200
    assert fail(client, "alice", 2) == [401, 401]
    assert login(client, "alice", GOOD).status_code == 200  # still not locked


def test_old_failures_do_not_accumulate(client_for, make_user):
    make_user("alice")
    client = client_for()
    fail(client, "alice", 2)
    LoginAttempt.objects.filter(identifier="alice").update(
        window_started_at=timezone.now() - timedelta(minutes=16)
    )
    assert fail(client, "alice", 2) == [401, 401]
    assert login(client, "alice", GOOD).status_code == 200


def test_unknown_usernames_are_locked_too(client_for):
    client = client_for()
    assert fail(client, "ghost", 3) == [401, 401, 401]
    assert login(client, "ghost", "anything").status_code == 429


def test_username_case_does_not_bypass_the_lock(client_for, make_user):
    make_user("alice")
    client = client_for()
    for name in ("alice", "ALICE", "Alice"):
        login(client, name, "wrong")
    assert login(client, "alice", GOOD).status_code == 429


def test_one_users_lock_does_not_affect_another(client_for, make_user):
    make_user("alice")
    make_user("bob")
    client = client_for()
    fail(client, "alice", 3)
    assert login(client, "bob", GOOD).status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"password": "x"},
        {"username": ["a"], "password": "x"},
        {"username": None, "password": "x"},
    ],
)
def test_malformed_logins_fail_cleanly(client_for, payload):
    res = client_for().post(LOGIN, payload, format="json")
    assert res.status_code == 400
    assert not LoginAttempt.objects.exists()


# ---- logout and refresh tokens -----------------------------------------

def test_logout_blacklists_the_refresh_token(client_for, make_user):
    make_user("alice")
    client = client_for()
    pair = tokens(client)
    assert client.post(LOGOUT, {"refresh": pair["refresh"]}, format="json").status_code == 204
    assert client.post(REFRESH, {"refresh": pair["refresh"]}, format="json").status_code == 401


def test_logout_rejects_missing_and_invalid_tokens(client_for):
    client = client_for()
    for body in ({}, {"refresh": ""}, {"refresh": "nonsense"}, {"refresh": 123}):
        assert client.post(LOGOUT, body, format="json").status_code == 400


def test_logging_out_twice_is_rejected_cleanly(client_for, make_user):
    make_user("alice")
    client = client_for()
    pair = tokens(client)
    assert client.post(LOGOUT, {"refresh": pair["refresh"]}, format="json").status_code == 204
    assert client.post(LOGOUT, {"refresh": pair["refresh"]}, format="json").status_code == 400


def test_a_used_refresh_token_cannot_be_reused(client_for, make_user):
    make_user("alice")
    client = client_for()
    pair = tokens(client)
    rotated = client.post(REFRESH, {"refresh": pair["refresh"]}, format="json").json()
    assert "refresh" in rotated
    assert client.post(REFRESH, {"refresh": pair["refresh"]}, format="json").status_code == 401
    assert client.post(REFRESH, {"refresh": rotated["refresh"]}, format="json").status_code == 200


def test_logout_only_ends_that_session(client_for, make_user):
    make_user("alice")
    client = client_for()
    first, second = tokens(client), tokens(client)
    client.post(LOGOUT, {"refresh": first["refresh"]}, format="json")
    assert client.post(REFRESH, {"refresh": second["refresh"]}, format="json").status_code == 200


# ---- unique email (only if you did step 6) ------------------------------

def test_database_rejects_duplicate_emails_ignoring_case():
    User.objects.create_user("a", "same@example.com", "pw12345678!")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            User.objects.create_user("b", "SAME@example.com", "pw12345678!")


def test_blank_emails_are_allowed_repeatedly():
    User.objects.create_user("c", "", "pw12345678!")
    User.objects.create_user("d", "", "pw12345678!")