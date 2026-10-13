import pytest

from learning.models import (
    PlacementAssessment,
    PlacementAttempt,
    PracticeSession,
    Question,
    QuestionAttempt,
    SchoolMembership,
    Student,
)

pytestmark = pytest.mark.django_db
Role = SchoolMembership.Role
STUDENTS = "/api/students/"


def ids(res):
    data = res.json()
    rows = data["results"] if isinstance(data, dict) else data
    return [r["id"] for r in rows]


def link_url(student):
    return f"{STUDENTS}{student.id}/link-user/"


def unlink_url(student):
    return f"{STUDENTS}{student.id}/unlink-user/"


@pytest.fixture
def classmate(school_a):
    return Student.objects.create(
        name="Chitra", email="chitra@example.com", school=school_a
    )


@pytest.fixture
def student_user(make_user, school_a, student_a):
    user = make_user("asha_login", school_a, Role.STUDENT)
    student_a.user = user
    student_a.save()
    return user


@pytest.fixture
def unlinked_login(make_user, school_a):
    return make_user("new_kid", school_a, Role.STUDENT)


# ---- what a linked student can see -------------------------------------

def test_student_sees_only_their_own_record(
    client_for, student_user, student_a, classmate, student_b
):
    res = client_for(student_user).get(STUDENTS)
    assert res.status_code == 200
    assert ids(res) == [student_a.id]


def test_student_cannot_read_a_classmate(client_for, student_user, classmate):
    assert client_for(student_user).get(f"{STUDENTS}{classmate.id}/").status_code == 404


def test_student_sees_only_their_own_sessions(
    client_for, student_user, student_a, classmate
):
    mine = PracticeSession.objects.create(student=student_a)
    PracticeSession.objects.create(student=classmate)
    res = client_for(student_user).get("/api/practice-sessions/")
    assert ids(res) == [mine.id]


def test_student_sees_only_their_own_attempts(
    client_for, student_user, student_a, classmate
):
    q = Question.objects.create(text="2 + 2?", answer="4")
    mine = QuestionAttempt.objects.create(
        question=q,
        practice_session=PracticeSession.objects.create(student=student_a),
        answer_given="4",
    )
    QuestionAttempt.objects.create(
        question=q,
        practice_session=PracticeSession.objects.create(student=classmate),
        answer_given="4",
    )
    res = client_for(student_user).get("/api/question-attempts/")
    assert ids(res) == [mine.id]


def test_student_sees_only_their_own_placement_data(
    client_for, student_user, student_a, classmate
):
    q = Question.objects.create(text="2 + 2?", answer="4")
    mine = PlacementAssessment.objects.create(student=student_a)
    theirs = PlacementAssessment.objects.create(student=classmate)
    my_attempt = PlacementAttempt.objects.create(
        assessment=mine, question=q, answer_given="4"
    )
    PlacementAttempt.objects.create(assessment=theirs, question=q, answer_given="4")

    client = client_for(student_user)
    assert ids(client.get("/api/placement-assessments/")) == [mine.id]
    assert ids(client.get("/api/placement-attempts/")) == [my_attempt.id]


# ---- what a linked student cannot do -----------------------------------

def test_student_cannot_write_or_delete_their_record(
    client_for, student_user, student_a, school_a
):
    client = client_for(student_user)
    body = {"name": "X", "email": "x@example.com", "school": school_a.id}
    assert client.post(STUDENTS, body, format="json").status_code == 403
    assert client.patch(
        f"{STUDENTS}{student_a.id}/", {"name": "Hacked"}, format="json"
    ).status_code == 403
    assert client.delete(f"{STUDENTS}{student_a.id}/").status_code == 403
    student_a.refresh_from_db()
    assert student_a.name == "Asha"


@pytest.mark.parametrize(
    "url",
    [
        "/api/practice-sessions/",
        "/api/question-attempts/",
        "/api/placement-assessments/",
        "/api/placement-attempts/",
    ],
)
def test_student_cannot_create_records(client_for, student_user, url):
    assert client_for(student_user).post(url, {}, format="json").status_code == 403


def test_student_cannot_analyze(client_for, student_user, student_a):
    assessment = PlacementAssessment.objects.create(student=student_a)
    res = client_for(student_user).get(
        f"/api/placement-assessments/{assessment.id}/analyze/"
    )
    assert res.status_code == 403


def test_student_cannot_read_question_bank(client_for, student_user):
    assert client_for(student_user).get("/api/questions/").status_code == 403


def test_student_loses_access_when_membership_removed(
    client_for, student_user, school_a
):
    SchoolMembership.objects.filter(user=student_user, school=school_a).delete()
    assert client_for(student_user).get(STUDENTS).status_code == 403


# ---- linking a login to a student --------------------------------------

def test_admin_can_link_a_student_login(
    client_for, admin_a, student_a, unlinked_login
):
    res = client_for(admin_a).post(
        link_url(student_a), {"email": unlinked_login.email}, format="json"
    )
    assert res.status_code == 200
    student_a.refresh_from_db()
    assert student_a.user_id == unlinked_login.id


def test_teacher_cannot_link(client_for, teacher_a, student_a, unlinked_login):
    res = client_for(teacher_a).post(
        link_url(student_a), {"email": unlinked_login.email}, format="json"
    )
    assert res.status_code == 403
    student_a.refresh_from_db()
    assert student_a.user_id is None


def test_cannot_link_user_without_student_membership(
    client_for, admin_a, student_a, make_user
):
    nobody = make_user("nomember")
    res = client_for(admin_a).post(
        link_url(student_a), {"email": nobody.email}, format="json"
    )
    assert res.status_code == 400
    student_a.refresh_from_db()
    assert student_a.user_id is None


def test_cannot_link_user_from_another_school(
    client_for, admin_a, student_a, make_user, school_b
):
    other = make_user("other_kid", school_b, Role.STUDENT)
    res = client_for(admin_a).post(
        link_url(student_a), {"email": other.email}, format="json"
    )
    assert res.status_code == 400


def test_cannot_link_unknown_email(client_for, admin_a, student_a):
    res = client_for(admin_a).post(
        link_url(student_a), {"email": "ghost@example.com"}, format="json"
    )
    assert res.status_code == 400


def test_cannot_link_a_login_already_used_by_another_student(
    client_for, admin_a, classmate, student_user
):
    res = client_for(admin_a).post(
        link_url(classmate), {"email": student_user.email}, format="json"
    )
    assert res.status_code == 400
    classmate.refresh_from_db()
    assert classmate.user_id is None


def test_admin_of_another_school_cannot_link(
    client_for, make_user, school_b, student_a, unlinked_login
):
    admin_b = make_user("admin_b", school_b, Role.ADMIN)
    res = client_for(admin_b).post(
        link_url(student_a), {"email": unlinked_login.email}, format="json"
    )
    assert res.status_code == 404


def test_admin_can_unlink(client_for, admin_a, student_a, student_user):
    res = client_for(admin_a).post(unlink_url(student_a))
    assert res.status_code == 200
    student_a.refresh_from_db()
    assert student_a.user_id is None


def test_teacher_cannot_unlink(client_for, teacher_a, student_a, student_user):
    assert client_for(teacher_a).post(unlink_url(student_a)).status_code == 403
    student_a.refresh_from_db()
    assert student_a.user_id == student_user.id


def test_user_cannot_be_set_through_patch(
    client_for, admin_a, student_a, unlinked_login
):
    client_for(admin_a).patch(
        f"{STUDENTS}{student_a.id}/", {"user": unlinked_login.id}, format="json"
    )
    student_a.refresh_from_db()
    assert student_a.user_id is None


# ---- /auth/me/ ----------------------------------------------------------

def test_me_reports_the_linked_student(client_for, student_user, student_a):
    res = client_for(student_user).get("/api/auth/me/")
    assert res.json()["student_id"] == student_a.id


def test_me_reports_no_student_for_staff(client_for, teacher_a):
    assert client_for(teacher_a).get("/api/auth/me/").json()["student_id"] is None