from rest_framework import serializers
from .models import Question, Student, PracticeSession


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = "__all__"

class PracticeSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PracticeSession
        fields = "__all__"

class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = "__all__"