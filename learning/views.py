from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .access import (
    AdminOnlyDeleteMixin,
    IsPlatformSuperuserOrReadOnly,
    IsSchoolMember,
    IsSchoolStaff,
    IsStaffOrLinkedStudentReadOnly,
    filter_to_user_schools,
    is_school_admin,
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
    LinkStudentUserSerializer,
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
    permission_classes = [IsAuthenticated, IsStaffOrLinkedStudentReadOnly]

    def school_id_of(self, instance):
        return instance.school_id

    def get_queryset(self):
        return filter_to_user_schools(
            super().get_queryset(),
            self.request.user,
            "school_id",
            "pk",
        )

    def _require_admin(self, student):
        if not is_school_admin(self.request.user, student.school_id):
            raise PermissionDenied("Only a school administrator can do this.")

    @action(detail=True, methods=["post"], url_path="link-user")
    def link_user(self, request, pk=None):
        student = self.get_object()
        self._require_admin(student)
        serializer = LinkStudentUserSerializer(
            data=request.data, context={"student": student}
        )
        serializer.is_valid(raise_exception=True)
        student.user = serializer.validated_data["user"]
        student.save(update_fields=["user"])
        return Response(self.get_serializer(student).data)

    @action(detail=True, methods=["post"], url_path="unlink-user")
    def unlink_user(self, request, pk=None):
        student = self.get_object()
        self._require_admin(student)
        student.user = None
        student.save(update_fields=["user"])
        return Response(self.get_serializer(student).data)


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
    permission_classes = [IsAuthenticated, IsStaffOrLinkedStudentReadOnly]

    def school_id_of(self, instance):
        return instance.student.school_id

    def get_queryset(self):
        return filter_to_user_schools(
            super().get_queryset(),
            self.request.user,
            "student__school_id",
            "student_id",
        )


class QuestionAttemptViewSet(AppendOnlyViewSet):
    queryset = QuestionAttempt.objects.all()
    serializer_class = QuestionAttemptSerializer
    permission_classes = [IsAuthenticated, IsStaffOrLinkedStudentReadOnly]

    def get_queryset(self):
        return filter_to_user_schools(
            super().get_queryset(),
            self.request.user,
            "practice_session__student__school_id",
            "practice_session__student_id",
        )


class PlacementAssessmentViewSet(AdminOnlyDeleteMixin, viewsets.ModelViewSet):
    queryset = PlacementAssessment.objects.all()
    serializer_class = PlacementAssessmentSerializer
    permission_classes = [IsAuthenticated, IsStaffOrLinkedStudentReadOnly]

    def school_id_of(self, instance):
        return instance.student.school_id

    def get_queryset(self):
        return filter_to_user_schools(
            super().get_queryset(),
            self.request.user,
            "student__school_id",
            "student_id",
        )

    @action(
        detail=True,
        methods=["get"],
        permission_classes=[IsAuthenticated, IsSchoolStaff],
    )
    def analyze(self, request, pk=None):
        assessment = self.get_object()
        result = analyze_placement(assessment.pk)
        return Response(result)


class PlacementAttemptViewSet(AppendOnlyViewSet):
    queryset = PlacementAttempt.objects.all()
    serializer_class = PlacementAttemptSerializer
    permission_classes = [IsAuthenticated, IsStaffOrLinkedStudentReadOnly]

    def get_queryset(self):
        return filter_to_user_schools(
            super().get_queryset(),
            self.request.user,
            "assessment__student__school_id",
            "assessment__student_id",
        )