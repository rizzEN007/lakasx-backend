import pytest

from learning.models import (
    PlacementAttempt,
    PlacementAssessment, 
    PracticeSession, 
    SchoolMembership, 
    Student,Question, 
    QuestionAttempt,
)

pytestmark = pytest.mark.django_db
Role = SchoolMembership.Role

STUDENTS = "/api/students/"
CURRICULUM = ["/api/levels/", "/api/topics/", "/api/questions/"]
SCHOOL_DATA = [
    STUDENTS,
    "/api/practice-sessions/",
    "/api/question-attempts/",
    "/api/placement-assessments/",
    "/api/placement-attempts/",
]


@pytest.fixture
def student_member(make_user, school_a):
    return make_user("student_member", school_a, Role.STUDENT)


@pytest.mark.parametrize("url", SCHOOL_DATA + CURRICULUM)
def test_unauthenticated_gets_401(client_for, url):
    assert client_for().get(url).status_code == 401


@pytest.mark.parametrize("url", SCHOOL_DATA + CURRICULUM)
def test_user_without_membership_gets_403(client_for, outsider, url):
    assert client_for(outsider).get(url).status_code == 403


@pytest.mark.parametrize("url", SCHOOL_DATA)
def test_student_role_gets_403_on_school_data(client_for, student_member, url):
    # Student-role access is intentionally not implemented yet.
    assert client_for(student_member).get(url).status_code == 403


def test_any_member_can_read_levels_and_topics(client_for, student_member):
    client = client_for(student_member)
    assert client.get("/api/levels/").status_code == 200
    assert client.get("/api/topics/").status_code == 200


def test_student_role_cannot_read_question_bank(client_for, student_member):
    assert client_for(student_member).get("/api/questions/").status_code == 403


def test_staff_can_read_questions(client_for, teacher_a):
    assert client_for(teacher_a).get("/api/questions/").status_code == 200


def test_teacher_cannot_write_curriculum(client_for, teacher_a):
    res = client_for(teacher_a).post(
        "/api/levels/", {"name": "L9", "order": 9}, format="json"
    )
    assert res.status_code == 403


def test_teacher_cannot_delete_student(client_for, teacher_a, student_a):
    res = client_for(teacher_a).delete(f"{STUDENTS}{student_a.id}/")
    assert res.status_code == 403
    assert Student.objects.filter(pk=student_a.pk).exists()


def test_admin_can_delete_student(client_for, admin_a, student_a):
    assert client_for(admin_a).delete(f"{STUDENTS}{student_a.id}/").status_code == 204
    assert not Student.objects.filter(pk=student_a.pk).exists()


def test_admin_cannot_delete_other_school_student(client_for, admin_a, student_b):
    assert client_for(admin_a).delete(f"{STUDENTS}{student_b.id}/").status_code == 404
    assert Student.objects.filter(pk=student_b.pk).exists()


def test_teacher_cannot_delete_practice_session(client_for, teacher_a, student_a):
    session = PracticeSession.objects.create(student=student_a)
    res = client_for(teacher_a).delete(f"/api/practice-sessions/{session.id}/")
    assert res.status_code == 403
    assert PracticeSession.objects.filter(pk=session.pk).exists()


def test_teacher_cannot_delete_placement_assessment(client_for, teacher_a, student_a):
    assessment = PlacementAssessment.objects.create(student=student_a)
    res = client_for(teacher_a).delete(f"/api/placement-assessments/{assessment.id}/")
    assert res.status_code == 403
    assert PlacementAssessment.objects.filter(pk=assessment.pk).exists()

def _ids(res):
    data = res.json()
    rows = data["results"] if isinstance(data, dict) else data
    return [r["id"] for r in rows]


def test_question_attempt_list_only_shows_own_school(
    client_for, teacher_a, student_a, student_b
):
    q = Question.objects.create(text="2 + 2?", answer="4")
    mine = QuestionAttempt.objects.create(
        question=q,
        practice_session=PracticeSession.objects.create(student=student_a),
        answer_given="4",
    )
    QuestionAttempt.objects.create(
        question=q,
        practice_session=PracticeSession.objects.create(student=student_b),
        answer_given="4",
    )
    res = client_for(teacher_a).get("/api/question-attempts/")
    assert _ids(res) == [mine.id]


def test_placement_attempt_list_only_shows_own_school(
    client_for, teacher_a, student_a, student_b
):
    q = Question.objects.create(text="2 + 2?", answer="4")
    mine = PlacementAttempt.objects.create(
        assessment=PlacementAssessment.objects.create(student=student_a),
        question=q,
        answer_given="4",
    )
    PlacementAttempt.objects.create(
        assessment=PlacementAssessment.objects.create(student=student_b),
        question=q,
        answer_given="4",
    )
    res = client_for(teacher_a).get("/api/placement-attempts/")
    assert _ids(res) == [mine.id]


def test_placement_attempts_are_append_only(client_for, admin_a, student_a):
    q = Question.objects.create(text="2 + 2?", answer="4")
    attempt = PlacementAttempt.objects.create(
        assessment=PlacementAssessment.objects.create(student=student_a),
        question=q,
        answer_given="4",
    )
    client = client_for(admin_a)
    url = f"/api/placement-attempts/{attempt.id}/"
    assert client.patch(url, {"answer_given": "5"}, format="json").status_code == 405
    assert client.delete(url).status_code == 405