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
        fields = "__all__"

class PlacementAssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlacementAssessment
        fields = "__all__"  

class PlacementAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlacementAttempt
        fields = "__all__"