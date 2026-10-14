from datetime import date, timedelta

import pytest
from django.utils import timezone

from learning.models import DailyActivity, Question, SchoolMembership, Student
from learning.services.streaks import effective_streak, record_activity, streak_status

pytestmark = pytest.mark.django_db
Role = SchoolMembership.Role
D = date(2026, 10, 14)


@pytest.fixture(autouse=True)
def _goal(settings):
    settings.DAILY_GOAL_QUESTIONS = 2


def answer_n(student, n, day, xp=10):
    return [record_activity(student, xp, today=day) for _ in range(n)]


@pytest.fixture
def kid(make_user, school_a, student_a):
    user = make_user("kid", school_a, Role.STUDENT)
    student_a.user = user
    student_a.grade = 4
    student_a.save()
    return user


def make_questions(n):
    return [
        Question.objects.create(text=f"{i}+{i}?", answer=str(2 * i), grade=4)
        for i in range(1, n + 1)
    ]


def play(client, n):
    results = []
    for _ in range(n):
        qid = client.post("/api/practice/next-question/").json()["question"]["id"]
        correct = Question.objects.get(pk=qid).answer
        results.append(
            client.post(
                "/api/practice/answer/", {"answer_given": correct}, format="json"
            ).json()
        )
    return results


# ---- streak logic -------------------------------------------------------

def test_meeting_the_goal_starts_a_streak(student_a):
    assert answer_n(student_a, 2, D) == [False, True]
    student_a.refresh_from_db()
    assert student_a.streak_count == 1
    assert student_a.longest_streak == 1
    assert student_a.last_goal_date == D


def test_below_the_goal_does_not_start_a_streak(student_a):
    record_activity(student_a, 10, today=D)
    student_a.refresh_from_db()
    assert student_a.streak_count == 0
    assert student_a.last_goal_date is None


def test_extra_answers_the_same_day_do_not_extend_again(student_a):
    answer_n(student_a, 5, D)
    student_a.refresh_from_db()
    assert student_a.streak_count == 1
    activity = DailyActivity.objects.get(student=student_a, date=D)
    assert activity.questions_answered == 5
    assert activity.xp_earned == 50


def test_consecutive_days_build_the_streak(student_a):
    for i in range(3):
        answer_n(student_a, 2, D + timedelta(days=i))
    student_a.refresh_from_db()
    assert student_a.streak_count == 3
    assert student_a.longest_streak == 3


def test_a_missed_day_resets_the_streak_but_keeps_the_record(student_a):
    answer_n(student_a, 2, D)
    answer_n(student_a, 2, D + timedelta(days=1))
    answer_n(student_a, 2, D + timedelta(days=3))  # skipped D+2
    student_a.refresh_from_db()
    assert student_a.streak_count == 1
    assert student_a.longest_streak == 2


def test_effective_streak_expires_after_a_missed_day(student_a):
    answer_n(student_a, 2, D)
    student_a.refresh_from_db()
    assert effective_streak(student_a, today=D) == 1
    assert effective_streak(student_a, today=D + timedelta(days=1)) == 1  # alive
    assert effective_streak(student_a, today=D + timedelta(days=2)) == 0  # broken


def test_streak_is_at_risk_until_todays_goal_is_met(student_a):
    answer_n(student_a, 2, D)
    student_a.refresh_from_db()
    tomorrow = D + timedelta(days=1)

    before = streak_status(student_a, today=tomorrow)
    assert before["current"] == 1
    assert before["at_risk"] is True
    assert before["goal_met_today"] is False

    answer_n(student_a, 2, tomorrow)
    student_a.refresh_from_db()
    after = streak_status(student_a, today=tomorrow)
    assert after["current"] == 2
    assert after["at_risk"] is False
    assert after["goal_met_today"] is True
    assert after["questions_today"] == 2
    assert after["daily_goal"] == 2


def test_streaks_are_per_student(student_a, student_b):
    answer_n(student_a, 2, D)
    student_b.refresh_from_db()
    assert student_b.streak_count == 0


# ---- through the API ----------------------------------------------------

def test_answers_report_streak_progress(client_for, kid, settings):
    settings.PRACTICE_SESSION_LENGTH = 5
    make_questions(5)
    client = client_for(kid)
    client.post("/api/practice/start/")
    first, second, third = play(client, 3)
    assert first["streak_extended"] is False
    assert first["streak"]["questions_today"] == 1
    assert second["streak_extended"] is True
    assert second["streak"]["current"] == 1
    assert second["streak"]["goal_met_today"] is True
    assert third["streak_extended"] is False


def test_progress_endpoint_summarises_the_student(client_for, kid):
    body = client_for(kid).get("/api/practice/progress/").json()
    assert body["grade"] == 4
    assert body["total_xp"] == 0
    assert body["level"] == 1
    assert body["streak"]["current"] == 0
    assert body["streak"]["daily_goal"] == 2


def test_staff_cannot_use_the_student_progress_endpoint(client_for, teacher_a):
    assert client_for(teacher_a).get("/api/practice/progress/").status_code == 403


def test_student_record_shows_an_expiring_streak(client_for, teacher_a, student_a):
    today = timezone.localdate()
    url = f"/api/students/{student_a.id}/"
    Student.objects.filter(pk=student_a.pk).update(
        streak_count=5, longest_streak=9, last_goal_date=today - timedelta(days=1)
    )
    body = client_for(teacher_a).get(url).json()
    assert body["current_streak"] == 5
    assert body["longest_streak"] == 9

    Student.objects.filter(pk=student_a.pk).update(
        last_goal_date=today - timedelta(days=3)
    )
    body = client_for(teacher_a).get(url).json()
    assert body["current_streak"] == 0
    assert body["longest_streak"] == 9


def test_streak_fields_cannot_be_set_through_the_api(client_for, admin_a, student_a):
    client_for(admin_a).patch(
        f"/api/students/{student_a.id}/",
        {"longest_streak": 99, "current_streak": 99, "streak_count": 99},
        format="json",
    )
    student_a.refresh_from_db()
    assert student_a.streak_count == 0
    assert student_a.longest_streak == 0