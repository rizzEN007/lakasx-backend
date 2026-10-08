from rest_framework import serializers
from .models import (PlacementAssessment, Question, Student, PracticeSession, QuestionAttempt, Level, Topic, PlacementAttempt)


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = "__all__"

class LevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Level
        fields = "__all__"

class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = "__all__"

class PracticeSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PracticeSession
        fields = "__all__"

class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = "__all__"

class QuestionAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionAttempt
        fields = [
            "id",
            "question",
            "practice_session",
            "answer_given",
            "attempted_at",
            "is_correct",
        ]
        read_only_fields = ["attempted_at", "is_correct"]

    def create(self, validated_data):
            question = validated_data["question"]
            answer_given = validated_data["answer_given"]

            is_correct = (
                question.answer.strip().lower() 
                == answer_given.strip().lower()
            )

            return QuestionAttempt.objects.create(
            **validated_data,
            is_correct=is_correct,
            )
            

class PlacementAssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlacementAssessment
        fields = "__all__"  

class PlacementAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlacementAttempt
        fields = [
            "id",
            "assessment",
            "question",
            "answer_given",
            "is_correct",
            "attempted_at",
        ]
        read_only_fields = ["is_correct", "attempted_at"]

    def create(self, validated_data):
        question = validated_data["question"]
        answer_given = validated_data["answer_given"]

        is_correct = (
            answer_given.strip().lower()
            == question.answer.strip().lower()
        )

        return PlacementAttempt.objects.create(
            **validated_data,
            is_correct=is_correct,
        )