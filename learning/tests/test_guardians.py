from datetime import date, datetime, time, timedelta

import pytest
from django.utils import timezone

from learning.models import (
    DailyActivity,
    GuardianLink,
    PlacementAssessment,
    PracticeSession,
    Question,
    QuestionAttempt,
    SchoolMembership,
    Student,
    Topic,
)
from learning.services.reports import weekly_summary

pytestmark = pytest.mark.django_db
Role = SchoolMembership.Role
Rel = GuardianLink.Relationship

CHILDREN = "/api/parent/children/"
STUDENTS = "/api/students/"
INELIGIBLE = "This login cannot be linked as a guardian of this student."


def ids(res):
    data = res.json()
    rows = data["results"] if isinstance(data, dict) else data
    return [r["id"] for r in rows]


def guardians_url(student):
    return f"{STUDENTS}{student.id}/guardians/"


@pytest.fixture
def mum(make_user, school_a):
    return make_user("mum", school_a, Role.PARENT)


@pytest.fixture
def dad(make_user, school_a):
    return make_user("dad", school_a, Role.PARENT)


@pytest.fixture
def classmate(school_a):
    return Student.objects.create(
        name="Chitra", email="chitra@example.com", school=school_a, grade=4
    )


@pytest.fixture
def linked(mum, student_a):
    return GuardianLink.objects.create(
        student=student_a, user=mum, relationship=Rel.PRIMARY
    )


# ---- linking guardians (admin only) -------------------------------------

def test_admin_can_add_a_primary_guardian(client_for, admin_a, student_a, mum):
    res = client_for(admin_a).post(
        guardians_url(student_a),
        {"email": mum.email, "relationship": "PRIMARY"},
        format="json",
    )
    assert res.status_code == 201
    assert res.json()["relationship"] == "PRIMARY"
    assert GuardianLink.objects.filter(student=student_a, user=mum).exists()


def test_teacher_and_parent_cannot_add_guardians(
    client_for, teacher_a, linked, student_a, dad
):
    body = {"email": dad.email, "relationship": "SECONDARY"}
    url = guardians_url(student_a)
    assert client_for(teacher_a).post(url, body, format="json").status_code == 403
    assert client_for(linked.user).post(url, body, format="json").status_code == 403
    assert GuardianLink.objects.count() == 1


def test_admin_of_another_school_cannot_add_guardians(
    client_for, make_user, school_b, student_a, mum
):
    admin_b = make_user("admin_b", school_b, Role.ADMIN)
    res = client_for(admin_b).post(
        guardians_url(student_a),
        {"email": mum.email, "relationship": "PRIMARY"},
        format="json",
    )
    assert res.status_code == 404


@pytest.mark.parametrize(
    "who", ["student_role", "other_school_parent", "no_membership", "unknown"]
)
def test_cannot_link_an_ineligible_login(
    client_for, admin_a, student_a, make_user, school_a, school_b, who
):
    if who == "student_role":
        email = make_user("kidlogin", school_a, Role.STUDENT).email
    elif who == "other_school_parent":
        email = make_user("faraway", school_b, Role.PARENT).email
    elif who == "no_membership":
        email = make_user("nobody").email
    else:
        email = "ghost@example.com"

    res = client_for(admin_a).post(
        guardians_url(student_a),
        {"email": email, "relationship": "PRIMARY"},
        format="json",
    )
    assert res.status_code == 400
    assert res.json()["email"] == [INELIGIBLE]  # identical for every failure
    assert GuardianLink.objects.count() == 0


def test_a_student_has_at_most_one_primary_guardian(
    client_for, admin_a, student_a, linked, dad
):
    res = client_for(admin_a).post(
        guardians_url(student_a),
        {"email": dad.email, "relationship": "PRIMARY"},
        format="json",
    )
    assert res.status_code == 400
    assert "relationship" in res.json()


def test_a_student_has_at_most_one_secondary_guardian(
    client_for, admin_a, student_a, linked, dad, make_user, school_a
):
    aunt = make_user("aunt", school_a, Role.PARENT)
    client = client_for(admin_a)
    url = guardians_url(student_a)
    first = client.post(url, {"email": dad.email, "relationship": "SECONDARY"}, format="json")
    second = client.post(url, {"email": aunt.email, "relationship": "SECONDARY"}, format="json")
    assert first.status_code == 201
    assert second.status_code == 400


def test_the_same_login_cannot_be_linked_twice(
    client_for, admin_a, student_a, linked, mum
):
    res = client_for(admin_a).post(
        guardians_url(student_a),
        {"email": mum.email, "relationship": "SECONDARY"},
        format="json",
    )
    assert res.status_code == 400
    assert GuardianLink.objects.count() == 1


def test_admin_can_list_and_remove_guardians(client_for, admin_a, student_a, linked):
    client = client_for(admin_a)
    listed = client.get(guardians_url(student_a)).json()
    assert [g["id"] for g in listed] == [linked.id]
    assert listed[0]["email"] == linked.user.email
    res = client.delete(f"{guardians_url(student_a)}{linked.id}/")
    assert res.status_code == 204
    assert not GuardianLink.objects.exists()


def test_only_admins_can_list_or_remove_guardians(
    client_for, teacher_a, student_a, linked
):
    client = client_for(teacher_a)
    assert client.get(guardians_url(student_a)).status_code == 403
    assert client.delete(f"{guardians_url(student_a)}{linked.id}/").status_code == 403
    assert client_for(linked.user).get(guardians_url(student_a)).status_code == 403
    assert GuardianLink.objects.exists()


def test_guardian_cannot_be_removed_through_another_students_url(
    client_for, admin_a, linked, classmate
):
    res = client_for(admin_a).delete(f"{guardians_url(classmate)}{linked.id}/")
    assert res.status_code == 404
    assert GuardianLink.objects.exists()


# ---- what a parent can see ----------------------------------------------

def test_parent_sees_only_their_own_children(
    client_for, mum, linked, student_a, classmate
):
    res = client_for(mum).get(CHILDREN)
    assert res.status_code == 200
    body = res.json()
    assert [c["student_id"] for c in body] == [student_a.id]
    assert body[0]["relationship"] == "PRIMARY"
    assert {"grade", "total_xp", "level", "streak"} <= set(body[0])


def test_secondary_guardian_sees_the_child_too(client_for, dad, student_a):
    GuardianLink.objects.create(student=student_a, user=dad, relationship=Rel.SECONDARY)
    body = client_for(dad).get(CHILDREN).json()
    assert [c["relationship"] for c in body] == ["SECONDARY"]


def test_parent_cannot_open_an_unlinked_child(client_for, mum, linked, classmate):
    client = client_for(mum)
    assert client.get(f"{CHILDREN}{classmate.id}/").status_code == 404
    assert client.get(f"{CHILDREN}{classmate.id}/weekly-summary/").status_code == 404


def test_non_parents_cannot_use_parent_endpoints(client_for, teacher_a, outsider):
    assert client_for().get(CHILDREN).status_code == 401
    assert client_for(teacher_a).get(CHILDREN).status_code == 403
    assert client_for(outsider).get(CHILDREN).status_code == 403


def test_parent_reads_only_their_childs_student_record(
    client_for, mum, linked, student_a, classmate
):
    client = client_for(mum)
    assert ids(client.get(STUDENTS)) == [student_a.id]
    assert client.get(f"{STUDENTS}{classmate.id}/").status_code == 404


def test_parent_sees_child_sessions_attempts_and_results_only(
    client_for, mum, linked, student_a, classmate
):
    q = Question.objects.create(text="2+2?", answer="4", grade=4)
    mine = PracticeSession.objects.create(student=student_a)
    theirs = PracticeSession.objects.create(student=classmate)
    my_attempt = QuestionAttempt.objects.create(
        question=q, practice_session=mine, answer_given="4", is_correct=True
    )
    QuestionAttempt.objects.create(
        question=q, practice_session=theirs, answer_given="4", is_correct=True
    )
    client = client_for(mum)
    assert ids(client.get("/api/practice-sessions/")) == [mine.id]
    assert ids(client.get("/api/question-attempts/")) == [my_attempt.id]
    assert client.get(f"/api/practice-sessions/{mine.id}/results/").status_code == 200
    assert client.get(f"/api/practice-sessions/{theirs.id}/results/").status_code == 404


def test_parent_is_read_only(client_for, mum, linked, student_a, school_a):
    client = client_for(mum)
    assert client.patch(
        f"{STUDENTS}{student_a.id}/", {"name": "X"}, format="json"
    ).status_code == 403
    assert client.post(
        STUDENTS,
        {"name": "X", "email": "x@example.com", "school": school_a.id},
        format="json",
    ).status_code == 403
    assert client.delete(f"{STUDENTS}{student_a.id}/").status_code == 403
    student_a.refresh_from_db()
    assert student_a.name == "Asha"


def test_parent_cannot_reach_staff_only_or_student_only_endpoints(
    client_for, mum, linked, student_a
):
    assessment = PlacementAssessment.objects.create(student=student_a)
    client = client_for(mum)
    assert client.get("/api/questions/").status_code == 403
    assert client.get(
        f"/api/placement-assessments/{assessment.id}/analyze/"
    ).status_code == 403
    assert client.post("/api/practice/start/").status_code == 403


def test_parent_loses_access_when_their_membership_is_removed(
    client_for, mum, linked, school_a
):
    SchoolMembership.objects.filter(user=mum, school=school_a).delete()
    assert client_for(mum).get(CHILDREN).status_code == 403
    assert client_for(mum).get(STUDENTS).status_code == 403


def test_a_teacher_who_is_also_a_parent_elsewhere_cannot_edit_that_child(
    client_for, teacher_a, school_b, student_b
):
    SchoolMembership.objects.create(school=school_b, user=teacher_a, role=Role.PARENT)
    GuardianLink.objects.create(student=student_b, user=teacher_a, relationship=Rel.PRIMARY)
    client = client_for(teacher_a)
    assert client.get(f"{STUDENTS}{student_b.id}/").status_code == 200
    res = client.patch(f"{STUDENTS}{student_b.id}/", {"name": "Hacked"}, format="json")
    assert res.status_code == 404
    student_b.refresh_from_db()
    assert student_b.name == "Bikash"


def test_me_lists_the_parents_children(client_for, mum, linked, student_a):
    body = client_for(mum).get("/api/auth/me/").json()
    assert body["children"] == [
        {"student_id": student_a.id, "name": "Asha", "relationship": "PRIMARY"}
    ]
    assert body["student_id"] is None


# ---- weekly summary -----------------------------------------------------

def test_weekly_summary_totals_and_window(student_a):
    today = date(2026, 10, 14)

    def at(day, hour=10):
        return timezone.make_aware(datetime.combine(day, time(hour, 0)))

    session = PracticeSession.objects.create(student=student_a)
    PracticeSession.objects.filter(pk=session.pk).update(started_at=at(today, 9))

    fractions = Topic.objects.create(name="Fractions")
    q1 = Question.objects.create(text="a", answer="1", grade=4, topic=fractions)
    q2 = Question.objects.create(text="b", answer="2", grade=4)  # no topic

    def attempt(question, correct, day):
        made = QuestionAttempt.objects.create(
            question=question,
            practice_session=session,
            answer_given="x",
            is_correct=correct,
        )
        QuestionAttempt.objects.filter(pk=made.pk).update(attempted_at=at(day))

    attempt(q1, True, today)
    attempt(q1, False, today - timedelta(days=1))
    attempt(q2, True, today - timedelta(days=2))
    attempt(q1, True, today - timedelta(days=8))  # outside the window
    DailyActivity.objects.create(
        student=student_a, date=today, questions_answered=1, xp_earned=15
    )

    summary = weekly_summary(student_a, today=today)

    assert summary["period"] == {"start": date(2026, 10, 8), "end": today}
    assert len(summary["days"]) == 7
    assert summary["days"][-1]["date"] == today
    assert summary["days"][-1]["xp_earned"] == 15
    totals = summary["totals"]
    assert totals["questions_answered"] == 3
    assert totals["correct"] == 2
    assert totals["accuracy_percent"] == 66.7
    assert totals["xp_earned"] == 15
    assert totals["active_days"] == 1
    assert totals["sessions"] == 1
    assert [t["topic"] for t in summary["topics"]] == ["Fractions", "Uncategorized"]  # weakest first


def test_weekly_summary_endpoint(client_for, mum, linked, student_a):
    body = client_for(mum).get(f"{CHILDREN}{student_a.id}/weekly-summary/").json()
    assert body["student"]["id"] == student_a.id
    assert len(body["days"]) == 7
    assert {"totals", "topics", "streak", "period"} <= set(body)