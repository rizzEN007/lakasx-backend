import pytest

from learning.models import XPEvent
from learning.services.xp import award_xp, xp_progress

pytestmark = pytest.mark.django_db
STUDENTS = "/api/students/"


@pytest.fixture(autouse=True)
def _thresholds(settings):
    settings.XP_LEVEL_THRESHOLDS = [0, 100, 250]


def test_level_starts_at_one():
    assert xp_progress(0) == {"level": 1, "xp_to_next_level": 100}
    assert xp_progress(99) == {"level": 1, "xp_to_next_level": 1}


def test_level_up_at_threshold():
    assert xp_progress(100) == {"level": 2, "xp_to_next_level": 150}


def test_top_level_has_no_next():
    assert xp_progress(250) == {"level": 3, "xp_to_next_level": None}
    assert xp_progress(9999)["level"] == 3


def test_staff_can_set_grade(client_for, teacher_a, student_a):
    res = client_for(teacher_a).patch(
        f"{STUDENTS}{student_a.id}/", {"grade": 4}, format="json"
    )
    assert res.status_code == 200
    student_a.refresh_from_db()
    assert student_a.grade == 4


@pytest.mark.parametrize("bad", [0, 13, -1])
def test_grade_must_be_between_1_and_12(client_for, teacher_a, student_a, bad):
    res = client_for(teacher_a).patch(
        f"{STUDENTS}{student_a.id}/", {"grade": bad}, format="json"
    )
    assert res.status_code == 400
    student_a.refresh_from_db()
    assert student_a.grade is None


def test_teacher_cannot_set_grade_in_another_school(client_for, teacher_a, student_b):
    res = client_for(teacher_a).patch(
        f"{STUDENTS}{student_b.id}/", {"grade": 4}, format="json"
    )
    assert res.status_code == 404
    student_b.refresh_from_db()
    assert student_b.grade is None


def test_xp_cannot_be_set_through_the_api(client_for, admin_a, student_a):
    client_for(admin_a).patch(
        f"{STUDENTS}{student_a.id}/", {"total_xp": 999}, format="json"
    )
    student_a.refresh_from_db()
    assert student_a.total_xp == 0


def test_student_response_includes_xp_and_level(client_for, teacher_a, student_a):
    award_xp(student_a, 120, XPEvent.Reason.CORRECT_ANSWER)
    body = client_for(teacher_a).get(f"{STUDENTS}{student_a.id}/").json()
    assert body["total_xp"] == 120
    assert body["level"] == 2
    assert body["xp_to_next_level"] == 130  # 250 - 120


def test_award_xp_updates_total_and_logs_event(student_a):
    event = award_xp(student_a, 10, XPEvent.Reason.CORRECT_ANSWER)
    student_a.refresh_from_db()
    assert student_a.total_xp == 10
    assert event.student_id == student_a.id and event.amount == 10


def test_award_xp_accumulates(student_a):
    award_xp(student_a, 10, XPEvent.Reason.CORRECT_ANSWER)
    award_xp(student_a, 5, XPEvent.Reason.FIRST_TRY_BONUS)
    student_a.refresh_from_db()
    assert student_a.total_xp == 15
    assert XPEvent.objects.filter(student=student_a).count() == 2


@pytest.mark.parametrize("amount", [0, -5])
def test_award_xp_rejects_non_positive_amounts(student_a, amount):
    with pytest.raises(ValueError):
        award_xp(student_a, amount, XPEvent.Reason.CORRECT_ANSWER)
    assert not XPEvent.objects.exists()