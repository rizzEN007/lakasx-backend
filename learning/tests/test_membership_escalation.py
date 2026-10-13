import pytest
from django.contrib.auth import get_user_model

from learning.models import SchoolMembership

pytestmark = pytest.mark.django_db
Role = SchoolMembership.Role
User = get_user_model()


def members_url(school):
    return f"/api/schools/{school.id}/members/"


def member_url(school, membership):
    return f"/api/schools/{school.id}/members/{membership.id}/"


def membership_of(user, school):
    return SchoolMembership.objects.filter(user=user, school=school)


@pytest.fixture
def admin_a(make_user, school_a):
    return make_user("admin_a", school_a, Role.ADMIN)


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser("root", "root@example.com", "pass12345!")


@pytest.fixture
def outsider(make_user):
    return make_user("outsider")  # registered, belongs to no school


def test_members_endpoints_require_authentication(client_for, school_a):
    assert client_for().get(members_url(school_a)).status_code == 401


def test_teacher_cannot_list_members(client_for, teacher_a, school_a):
    assert client_for(teacher_a).get(members_url(school_a)).status_code == 403


def test_teacher_cannot_add_members(client_for, teacher_a, school_a, outsider):
    res = client_for(teacher_a).post(
        members_url(school_a),
        {"email": outsider.email, "role": "STUDENT"},
        format="json",
    )
    assert res.status_code == 403
    assert not membership_of(outsider, school_a).exists()


def test_admin_can_add_teacher_without_exposing_account_details(
    client_for, admin_a, school_a, outsider
):
    res = client_for(admin_a).post(
        members_url(school_a),
        {"email": outsider.email, "role": "TEACHER"},
        format="json",
    )
    assert res.status_code == 201
    body = res.json()
    assert "email" not in body and "username" not in body
    assert membership_of(outsider, school_a).get().role == "TEACHER"


def test_admin_cannot_grant_admin_role(client_for, admin_a, school_a, outsider):
    res = client_for(admin_a).post(
        members_url(school_a),
        {"email": outsider.email, "role": "ADMIN"},
        format="json",
    )
    assert res.status_code == 400
    assert "role" in res.json()
    assert not membership_of(outsider, school_a).exists()


def test_superuser_can_grant_admin_role(client_for, superuser, school_a, outsider):
    res = client_for(superuser).post(
        members_url(school_a),
        {"email": outsider.email, "role": "ADMIN"},
        format="json",
    )
    assert res.status_code == 201
    assert membership_of(outsider, school_a).get().role == "ADMIN"


def test_admin_cannot_manage_another_school(client_for, admin_a, school_b, outsider):
    client = client_for(admin_a)
    assert client.get(members_url(school_b)).status_code == 403
    res = client.post(
        members_url(school_b),
        {"email": outsider.email, "role": "TEACHER"},
        format="json",
    )
    assert res.status_code == 403
    assert not membership_of(outsider, school_b).exists()


def test_admin_cannot_remove_an_admin(client_for, admin_a, make_user, school_a):
    other_admin = make_user("admin_a2", school_a, Role.ADMIN)
    target = membership_of(other_admin, school_a).get()
    res = client_for(admin_a).delete(member_url(school_a, target))
    assert res.status_code == 403
    assert membership_of(other_admin, school_a).exists()


def test_admin_can_remove_a_teacher(client_for, admin_a, teacher_a, school_a):
    target = membership_of(teacher_a, school_a).get()
    res = client_for(admin_a).delete(member_url(school_a, target))
    assert res.status_code == 204
    assert not membership_of(teacher_a, school_a).exists()


def test_cannot_delete_membership_through_another_schools_url(
    client_for, admin_a, teacher_b, school_a, school_b
):
    target = membership_of(teacher_b, school_b).get()
    res = client_for(admin_a).delete(member_url(school_a, target))
    assert res.status_code == 404
    assert membership_of(teacher_b, school_b).exists()


def test_membership_role_cannot_be_edited(client_for, admin_a, teacher_a, school_a):
    target = membership_of(teacher_a, school_a).get()
    res = client_for(admin_a).patch(
        member_url(school_a, target), {"role": "ADMIN"}, format="json"
    )
    assert res.status_code == 405
    target.refresh_from_db()
    assert target.role == "TEACHER"


def test_cannot_add_by_user_id(client_for, admin_a, school_a, outsider):
    res = client_for(admin_a).post(
        members_url(school_a),
        {"user_id": outsider.id, "role": "TEACHER"},
        format="json",
    )
    assert res.status_code == 400
    assert not membership_of(outsider, school_a).exists()


def test_cannot_add_same_user_twice(client_for, admin_a, teacher_a, school_a):
    res = client_for(admin_a).post(
        members_url(school_a),
        {"email": teacher_a.email, "role": "TEACHER"},
        format="json",
    )
    assert res.status_code == 400


def test_registration_ignores_privileged_fields(client_for):
    res = client_for().post(
        "/api/auth/register/",
        {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "Str0ng-pass-phrase!42",
            "is_superuser": True,
            "is_staff": True,
        },
        format="json",
    )
    assert res.status_code == 201
    user = User.objects.get(username="newuser")
    assert not user.is_superuser and not user.is_staff