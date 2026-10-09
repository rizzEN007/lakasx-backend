from django.db.models import Count, Q

from ..models import PlacementAssessment

def analyze_placement(assessment_id):
    assessment = (
        PlacementAssessment.objects
        .select_related("student")
        .prefetch_related(
        "attempts__question__level",
        "attempts__question__topic",
        )
        .get(id=assessment_id)
    )

    attempts = assessment.attempts.all()

    total_questions = attempts.count()
    correct_answers = attempts.filter(is_correct=True).count()

    score_percentage = (
        (correct_answers / total_questions) * 100 
        if total_questions > 0 
        else 0
    )

    topic_performance = {}

    for attempt in attempts:
        topic_name = attempt.question.topic.name

        if topic_name not in topic_performance:
            topic_performance[topic_name] = {
                "total": 0,
                "correct": 0,
            }
            
        topic_performance[topic_name]["total"] += 1

        if attempt.is_correct:
            topic_performance[topic_name]["correct"] += 1

    for topic_name, data in topic_performance.items():
        total = data["percentage"] =(
        data["correct"] / data["total"]
        ) * 100

        level_performance = {}
    for attempt in attempts:
        level_name = attempt.question.level.name

        if level_name not in level_performance:
            level_performance[level_name] = {
                "total": 0,
                "correct": 0,
            }

        level_performance[level_name]["total"] += 1

        if attempt.is_correct:
            level_performance[level_name]["correct"] += 1
    for level_name, data in level_performance.items():
        data["percentage"] = (
            data["correct"] / data["total"]
        ) * 100

    return {
        "student": assessment.student.id,
        "assessment_id": assessment.id,
        "total_questions": total_questions,
        "correct_answers": correct_answers,
        "score_percentage": score_percentage,
        "topic_performance": topic_performance,
        "level_performance": level_performance,
    }