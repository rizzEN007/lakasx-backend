import pytest
from django.contrib.auth import get_user_model

from learning.models import School, SchoolMembership, Student

pytestmark = pytest.mark.django_db
User = get_user_model()
PW = "pass12345!"


@pytest.fixture
def two_schools():
    a = School.objects.create(name="Alpha", code="alpha")
    b = School.objects.create(name="Beta", code="beta")
    Student.objects.create(name="Ann Alpha", email="ann@a.test", school=a)
    Student.objects.create(name="Ben Beta", email="ben@b.test", school=b)
    return a, b


def member(username, school, role):
    user = User.objects.create_user(username, f"{username}@x.test", PW)
    SchoolMembership.objects.create(school=school, user=user, role=role)
    return user


def log_in(client, username, password=PW):
    return client.post("/portal/login/", {"username": username, "password": password})


def test_anonymous_is_sent_to_login(client):
    res = client.get("/portal/")
    assert res.status_code == 302
    assert "/portal/login/" in res["Location"]


def test_superuser_can_log_in_and_see_everything(client, two_schools):
    User.objects.create_superuser("root", "r@x.test", PW)
    assert log_in(client, "root").status_code == 302
    page = client.get("/portal/students/")
    assert page.status_code == 200
    assert b"Ann Alpha" in page.content and b"Ben Beta" in page.content


def test_teacher_only_sees_their_own_school(client, two_schools):
    a, _ = two_schools
    member("tina", a, "TEACHER")
    log_in(client, "tina")
    page = client.get("/portal/students/")
    assert b"Ann Alpha" in page.content
    assert b"Ben Beta" not in page.content


def test_other_schools_student_is_a_404(client, two_schools):
    a, b = two_schools
    member("tina", a, "TEACHER")
    log_in(client, "tina")
    other = Student.objects.get(school=b)
    assert client.get(f"/portal/students/{other.pk}/").status_code == 404
    mine = Student.objects.get(school=a)
    assert client.get(f"/portal/students/{mine.pk}/").status_code == 200


def test_student_role_and_no_membership_are_refused(client, two_schools):
    a, _ = two_schools
    member("sam", a, "STUDENT")
    User.objects.create_user("nobody", "n@x.test", PW)
    for name in ("sam", "nobody"):
        client.logout()
        log_in(client, name)
        assert client.get("/portal/").status_code == 403


def test_wrong_password_shows_an_error(client, two_schools):
    User.objects.create_user("bob", "b@x.test", PW)
    res = log_in(client, "bob", "wrong")
    assert res.status_code == 200
    assert b"Please enter a correct" in res.content


def test_logout_needs_post_and_ends_the_session(client, two_schools):
    User.objects.create_superuser("root", "r@x.test", PW)
    log_in(client, "root")
    assert client.post("/portal/logout/").status_code == 302
    assert client.get("/portal/").status_code == 302


def test_portal_login_shares_the_account_lock(client, settings):
    pytest.importorskip("learning.services.lockout")
    settings.LOGIN_MAX_FAILURES = 3
    User.objects.create_user("bob", "b@x.test", PW)
    for _ in range(3):
        log_in(client, "bob", "wrong")
    res = log_in(client, "bob")  # right password, still refused
    assert res.status_code == 429
    assert b"Too many failed attempts" in res.content


def test_only_superusers_can_unlock(client, two_schools):
    pytest.importorskip("learning.services.lockout")
    a, _ = two_schools
    member("tina", a, "TEACHER")
    log_in(client, "tina")
    assert client.get("/portal/locked/").status_code == 403
