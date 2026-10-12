from ..models import PlacementAssessment

UNCATEGORIZED = "Uncategorized"
UNLEVELED = "Unleveled"


def _bucket(stats, name, is_correct):
    entry = stats.setdefault(name, {"total": 0, "correct": 0})
    entry["total"] += 1
    if is_correct:
        entry["correct"] += 1


def _add_percentages(stats):
    for entry in stats.values():
        entry["percentage"] = entry["correct"] / entry["total"] * 100


def analyze_placement(assessment_id):
    assessment = (
        PlacementAssessment.objects
        .select_related("student")
        .prefetch_related("attempts__question__level", "attempts__question__topic")
        .get(id=assessment_id)
    )

    # Evaluate once so the prefetch is used; count in Python, not with extra queries.
    attempts = list(assessment.attempts.all())
    total_questions = len(attempts)
    correct_answers = sum(1 for a in attempts if a.is_correct)
    score_percentage = (
        correct_answers / total_questions * 100 if total_questions else 0
    )

    topic_performance = {}
    level_performance = {}
    for attempt in attempts:
        question = attempt.question
        topic_name = question.topic.name if question.topic else UNCATEGORIZED
        level_name = question.level.name if question.level else UNLEVELED
        _bucket(topic_performance, topic_name, attempt.is_correct)
        _bucket(level_performance, level_name, attempt.is_correct)

    _add_percentages(topic_performance)
    _add_percentages(level_performance)

    return {
        "student": assessment.student.id,
        "assessment_id": assessment.id,
        "total_questions": total_questions,
        "correct_answers": correct_answers,
        "score_percentage": score_percentage,
        "topic_performance": topic_performance,
        "level_performance": level_performance,
    }