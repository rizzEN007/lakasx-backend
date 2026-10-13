from rest_framework import serializers
from django.contrib.auth import get_user_model

from .access import can_access_school, STAFF_ROLES
from .models import (
    PlacementAssessment,
    PlacementAttempt,
    Question,
    Student,
    PracticeSession,
    QuestionAttempt,
    Level,
    Topic,
    SchoolMembership,
)

User = get_user_model()

class SchoolScopedSerializerMixin:
    def can_access_school(self, school_id):
        request = self.context.get("request")
        return bool(
            request
            and request.user.is_authenticated
            and can_access_school(request.user, school_id)
        )


class StudentSerializer(
    SchoolScopedSerializerMixin,
    serializers.ModelSerializer,
):
    class Meta:
        model = Student
        fields = ["id", "name", "email", "school","created_at"]
        read_only_fields = ["id", "created_at", "user"]

    def validate_school(self, school):
        if not self.can_access_school(school.pk):
            raise serializers.ValidationError(
                "You cannot manage students for this school."
            )

        if self.instance and school.pk != self.instance.school_id:
            raise serializers.ValidationError(
                "Changing a student's school requires a dedicated transfer workflow."
            )

        return school


class LevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Level
        fields = "__all__"


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = "__all__"


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = "__all__"

    def _sees_answers(self):
        if not hasattr(self, "_sees_answers_cache"):
            request = self.context.get("request")
            user = getattr(request, "user", None)
            self._sees_answers_cache = bool(
                user
                and user.is_authenticated
                and (
                    user.is_superuser
                    or SchoolMembership.objects.filter(
                        user=user, role__in=STAFF_ROLES
                    ).exists()
                )
            )
        return self._sees_answers_cache

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self._sees_answers():
            data["answer"] = None
        return data


class PracticeSessionSerializer(
    SchoolScopedSerializerMixin,
    serializers.ModelSerializer,
):
    class Meta:
        model = PracticeSession
        fields = "__all__"
        read_only_fields = ["id", "started_at"]

    def validate_student(self, student):
        if not self.can_access_school(student.school_id):
            raise serializers.ValidationError(
                "You cannot create or manage sessions for this student."
            )
        return student


class QuestionAttemptSerializer(
    SchoolScopedSerializerMixin,
    serializers.ModelSerializer,
):
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
        read_only_fields = ["id", "attempted_at", "is_correct"]

    def validate_practice_session(self, session):
        if not self.can_access_school(session.student.school_id):
            raise serializers.ValidationError(
                "You cannot access this practice session."
            )
        return session

    def create(self, validated_data):
        question = validated_data["question"]
        answer_given = validated_data["answer_given"]

        expected = question.answer
        is_correct = (
            expected is not None
            and expected.strip().casefold() == answer_given.strip().casefold()
        )

        return QuestionAttempt.objects.create(
            **validated_data,
            is_correct=is_correct,
        )


class PlacementAssessmentSerializer(
    SchoolScopedSerializerMixin,
    serializers.ModelSerializer,
):
    class Meta:
        model = PlacementAssessment
        fields = "__all__"
        read_only_fields = ["id", "started_at"]

    def validate_student(self, student):
        if not self.can_access_school(student.school_id):
            raise serializers.ValidationError(
                "You cannot create or manage assessments for this student."
            )
        return student


class PlacementAttemptSerializer(
    SchoolScopedSerializerMixin,
    serializers.ModelSerializer,
):
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
        read_only_fields = ["id", "is_correct", "attempted_at"]

    def validate_assessment(self, assessment):
        if not self.can_access_school(assessment.student.school_id):
            raise serializers.ValidationError(
                "You cannot access this placement assessment."
            )
        return assessment

    def create(self, validated_data):
        question = validated_data["question"]
        answer_given = validated_data["answer_given"]

        expected = question.answer
        is_correct = (
            expected is not None
            and expected.strip().casefold() == answer_given.strip().casefold()
        )

        return PlacementAttempt.objects.create(
            **validated_data,
            is_correct=is_correct,
        )
    
class LinkStudentUserSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate(self, attrs):
        student = self.context["student"]
        user = User.objects.filter(email__iexact=attrs["email"]).first()

        is_valid = (
            user is not None
            and SchoolMembership.objects.filter(
                user=user,
                school_id=student.school_id,
                role=SchoolMembership.Role.STUDENT,
            ).exists()
            and not Student.objects.filter(user=user).exclude(pk=student.pk).exists()
        )
        if not is_valid:
            # One message for every failure, so account existence isn't revealed.
            raise serializers.ValidationError(
                {"email": "This login cannot be linked to this student."}
            )

        attrs["user"] = user
        return attrs