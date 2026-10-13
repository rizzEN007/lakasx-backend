import pytest

from learning.models import (
    PracticeSession, 
    Question, 
    SchoolMembership, 
    Student,
    Level, 
    PlacementAssessment, 
    PlacementAttempt,
)

pytestmark = pytest.mark.django_db
STUDENTS = "/api/students/"
ATTEMPTS = "/api/question-attempts/"
ANALYZE = "/api/placement-assessments/{}/analyze/"


def ids(res):
    data = res.json()
    rows = data["results"] if isinstance(data, dict) else data
    return [r["id"] for r in rows]


def test_unauthenticated_gets_401(client_for):
    assert client_for().get(STUDENTS).status_code == 401


def test_list_only_shows_own_school(client_for, teacher_a, student_a, student_b):
    res = client_for(teacher_a).get(STUDENTS)
    assert res.status_code == 200
    assert ids(res) == [student_a.id]


def test_cannot_read_other_school_student(client_for, teacher_a, student_b):
    assert client_for(teacher_a).get(f"{STUDENTS}{student_b.id}/").status_code == 404


def test_cannot_update_other_school_student(client_for, teacher_a, student_b):
    res = client_for(teacher_a).patch(
        f"{STUDENTS}{student_b.id}/", {"name": "Hacked"}, format="json"
    )
    assert res.status_code == 404
    student_b.refresh_from_db()
    assert student_b.name == "Bikash"


def test_cannot_delete_other_school_student(client_for, teacher_a, student_b):
    assert client_for(teacher_a).delete(f"{STUDENTS}{student_b.id}/").status_code == 404
    assert Student.objects.filter(pk=student_b.pk).exists()


def test_cannot_create_student_in_other_school(client_for, teacher_a, school_b):
    res = client_for(teacher_a).post(
        STUDENTS,
        {"name": "X", "email": "x@example.com", "school": school_b.id},
        format="json",
    )
    assert res.status_code == 400
    assert not Student.objects.filter(email="x@example.com").exists()


def test_changing_a_students_school_is_rejected(
    client_for, make_user, school_a, school_b, student_a
):
    both = make_user("both", school_a, SchoolMembership.Role.TEACHER)
    SchoolMembership.objects.create(school=school_b, user=both, role="TEACHER")
    res = client_for(both).patch(
        f"{STUDENTS}{student_a.id}/", {"school": school_b.id}, format="json"
    )
    assert res.status_code == 400


def test_same_email_allowed_across_schools(
    client_for, teacher_a, teacher_b, school_a, school_b
):
    body = {"name": "Dup", "email": "shared@example.com"}
    assert client_for(teacher_a).post(
        STUDENTS, {**body, "school": school_a.id}, format="json"
    ).status_code == 201
    assert client_for(teacher_b).post(
        STUDENTS, {**body, "school": school_b.id}, format="json"
    ).status_code == 201


def test_duplicate_email_rejected_within_school(client_for, teacher_a, school_a):
    body = {"name": "Dup", "email": "same@example.com", "school": school_a.id}
    assert client_for(teacher_a).post(STUDENTS, body, format="json").status_code == 201
    assert client_for(teacher_a).post(STUDENTS, body, format="json").status_code == 400


def test_cannot_attach_attempt_to_other_school_session(client_for, teacher_a, student_b):
    question = Question.objects.create(text="What is 5 + 5?", answer="10")
    session = PracticeSession.objects.create(student=student_b)
    res = client_for(teacher_a).post(
        ATTEMPTS,
        {"question": question.id, "practice_session": session.id, "answer_given": "10"},
        format="json",
    )
    assert res.status_code == 400


@pytest.mark.parametrize("given,expected", [("10", True), ("  10 ", True), ("11", False)])
def test_is_correct_is_computed_server_side(
    client_for, teacher_a, student_a, given, expected
):
    question = Question.objects.create(text="What is 5 + 5?", answer="10")
    session = PracticeSession.objects.create(student=student_a)
    res = client_for(teacher_a).post(
        ATTEMPTS,
        {"question": question.id, "practice_session": session.id, "answer_given": given},
        format="json",
    )
    assert res.status_code == 201
    assert res.json()["is_correct"] is expected


# These two fail until fixes 1 and 2 are applied.
def test_attempts_are_append_only(client_for, teacher_a, student_a):
    question = Question.objects.create(text="What is 5 + 5?", answer="10")
    session = PracticeSession.objects.create(student=student_a)
    created = client_for(teacher_a).post(
        ATTEMPTS,
        {"question": question.id, "practice_session": session.id, "answer_given": "11"},
        format="json",
    ).json()
    res = client_for(teacher_a).patch(
        f"{ATTEMPTS}{created['id']}/", {"answer_given": "10"}, format="json"
    )
    assert res.status_code == 405


def test_login_is_throttled(client_for, make_user):
    make_user("someone")
    client = client_for()
    codes = [
        client.post(
            "/api/auth/login/",
            {"username": "someone", "password": "wrong"},
            format="json",
        ).status_code
        for _ in range(31)
    ]
    assert codes[-1] == 429

def test_cannot_analyze_other_school_assessment(client_for, teacher_a, student_b):
    assessment = PlacementAssessment.objects.create(student=student_b)
    res = client_for(teacher_a).get(ANALYZE.format(assessment.id))
    assert res.status_code == 404


def test_analyze_own_assessment_with_levels(client_for, teacher_a, student_a):
    level = Level.objects.create(name="L1", order=1)
    q = Question.objects.create(text="2 + 2?", answer="4", level=level)
    assessment = PlacementAssessment.objects.create(student=student_a)
    PlacementAttempt.objects.create(
        assessment=assessment, question=q, answer_given="4", is_correct=True
    )
    res = client_for(teacher_a).get(ANALYZE.format(assessment.id))
    assert res.status_code == 200


def test_analyze_handles_question_without_level(client_for, teacher_a, student_a):
    q = Question.objects.create(text="Unleveled?", answer="yes")  # level=None
    assessment = PlacementAssessment.objects.create(student=student_a)
    PlacementAttempt.objects.create(
        assessment=assessment, question=q, answer_given="yes", is_correct=True
    )
    res = client_for(teacher_a).get(ANALYZE.format(assessment.id))
    assert res.status_code == 200   

def test_duplicate_placement_attempt_rejected(client_for, teacher_a, student_a):
    q = Question.objects.create(text="2 + 2?", answer="4")
    assessment = PlacementAssessment.objects.create(student=student_a)
    body = {"assessment": assessment.id, "question": q.id, "answer_given": "4"}
    client = client_for(teacher_a)
    assert client.post("/api/placement-attempts/", body, format="json").status_code == 201
    assert client.post("/api/placement-attempts/", body, format="json").status_code == 400

def test_analyze_assessment_with_no_attempts(client_for, teacher_a, student_a):
    assessment = PlacementAssessment.objects.create(student=student_a)
    res = client_for(teacher_a).get(ANALYZE.format(assessment.id))
    assert res.status_code == 200
    body = res.json()
    assert body["total_questions"] == 0
    assert body["score_percentage"] == 0
    assert body["topic_performance"] == {}
    assert body["level_performance"] == {}    