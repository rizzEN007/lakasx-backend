from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .access import (
    AdminOnlyDeleteMixin,
    IsPlatformSuperuserOrReadOnly,
    IsSchoolMember,
    IsSchoolStaff,
    filter_to_user_schools,
)
from .services.placement import analyze_placement
from .models import (
    Student,
    Level,
    Topic,
    PracticeSession,
    Question,
    QuestionAttempt,
    PlacementAssessment,
    PlacementAttempt,
)
from .serializers import (
    QuestionSerializer,
    StudentSerializer,
    LevelSerializer,
    TopicSerializer,
    PracticeSessionSerializer,
    QuestionAttemptSerializer,
    PlacementAssessmentSerializer,
    PlacementAttemptSerializer,
)


class AppendOnlyViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Attempts are a record of what happened: create and read only."""


class StudentViewSet(AdminOnlyDeleteMixin, viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated, IsSchoolStaff]

    def school_id_of(self, instance):
        return instance.school_id

    def get_queryset(self):
        return filter_to_user_schools(
            super().get_queryset(),
            self.request.user,
            "school_id",
        )


class LevelViewSet(viewsets.ModelViewSet):
    queryset = Level.objects.all()
    serializer_class = LevelSerializer
    permission_classes = [
        IsAuthenticated,
        IsSchoolMember,
        IsPlatformSuperuserOrReadOnly,
    ]


class TopicViewSet(viewsets.ModelViewSet):
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer
    permission_classes = [
        IsAuthenticated,
        IsSchoolMember,
        IsPlatformSuperuserOrReadOnly,
    ]


class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    permission_classes = [
        IsAuthenticated,
        IsSchoolStaff,
        IsPlatformSuperuserOrReadOnly,
    ]


class PracticeSessionViewSet(AdminOnlyDeleteMixin, viewsets.ModelViewSet):
    queryset = PracticeSession.objects.all()
    serializer_class = PracticeSessionSerializer
    permission_classes = [IsAuthenticated, IsSchoolStaff]

    def school_id_of(self, instance):
        return instance.student.school_id

    def get_queryset(self):
        return filter_to_user_schools(
            super().get_queryset(),
            self.request.user,
            "student__school_id",
        )


class QuestionAttemptViewSet(AppendOnlyViewSet):
    queryset = QuestionAttempt.objects.all()
    serializer_class = QuestionAttemptSerializer
    permission_classes = [IsAuthenticated, IsSchoolStaff]

    def get_queryset(self):
        return filter_to_user_schools(
            super().get_queryset(),
            self.request.user,
            "practice_session__student__school_id",
        )


class PlacementAssessmentViewSet(AdminOnlyDeleteMixin, viewsets.ModelViewSet):
    queryset = PlacementAssessment.objects.all()
    serializer_class = PlacementAssessmentSerializer
    permission_classes = [IsAuthenticated, IsSchoolStaff]

    def school_id_of(self, instance):
        return instance.student.school_id

    def get_queryset(self):
        return filter_to_user_schools(
            super().get_queryset(),
            self.request.user,
            "student__school_id",
        )

    @action(detail=True, methods=["get"])
    def analyze(self, request, pk=None):
        assessment = self.get_object()
        result = analyze_placement(assessment.pk)
        return Response(result)


class PlacementAttemptViewSet(AppendOnlyViewSet):
    queryset = PlacementAttempt.objects.all()
    serializer_class = PlacementAttemptSerializer
    permission_classes = [IsAuthenticated, IsSchoolStaff]

    def get_queryset(self):
        return filter_to_user_schools(
            super().get_queryset(),
            self.request.user,
            "assessment__student__school_id",
        )