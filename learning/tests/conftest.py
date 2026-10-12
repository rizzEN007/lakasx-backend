import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from learning.models import School, SchoolMembership, Student

User = get_user_model()
Role = SchoolMembership.Role


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    cache.clear()  # throttle history would leak between tests


@pytest.fixture
def school_a(db):
    return School.objects.create(name="School A", code="school-a")


@pytest.fixture
def school_b(db):
    return School.objects.create(name="School B", code="school-b")


@pytest.fixture
def make_user(db):
    def _make(username, school=None, role=None):
        user = User.objects.create_user(username=username, password="pass12345!")
        if school and role:
            SchoolMembership.objects.create(school=school, user=user, role=role)
        return user
    return _make


@pytest.fixture
def client_for():
    def _client(user=None):
        client = APIClient()
        if user:
            client.force_authenticate(user)
        return client
    return _client


@pytest.fixture
def teacher_a(make_user, school_a):
    return make_user("teacher_a", school_a, Role.TEACHER)


@pytest.fixture
def teacher_b(make_user, school_b):
    return make_user("teacher_b", school_b, Role.TEACHER)


@pytest.fixture
def student_a(school_a):
    return Student.objects.create(name="Asha", email="asha@example.com", school=school_a)


@pytest.fixture
def student_b(school_b):
    return Student.objects.create(name="Bikash", email="bikash@example.com", school=school_b)