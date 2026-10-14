from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .services.streaks import streak_status
from .services.xp import xp_progress

from django.conf import settings

from .access import (
    AdminOnlyDeleteMixin,
    IsPlatformSuperuserOrReadOnly,
    IsSchoolMember,
    IsSchoolStaff,
    IsStaffOrLinkedStudentReadOnly,
    filter_to_user_schools,
    is_school_admin,
    linked_student,
    IsLinkedStudent,
)

from .services import practice
from .services.practice import PracticeError, session_results
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
    PracticeQuestionSerializer,
    PracticeAnswerSerializer,   
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


class PracticeSessionViewSet(
    AdminOnlyDeleteMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
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

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        return Response(session_results(self.get_object()))


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

class PracticeViewSet(viewsets.ViewSet):
    """The student's practice loop. The server controls what is served and scored."""

    permission_classes = [IsAuthenticated, IsLinkedStudent]

    @staticmethod
    def _conflict(error):
        return Response(
            {"code": error.code, "detail": error.message},
            status=status.HTTP_409_CONFLICT,
        )

    @action(detail=False, methods=["post"])
    def start(self, request):
        student = linked_student(request.user)
        try:
            session, created = practice.start_session(student)
        except PracticeError as error:
            return self._conflict(error)
        return Response(
            {
                "session_id": session.pk,
                "started_at": session.started_at,
                "session_length": settings.PRACTICE_SESSION_LENGTH,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="next-question")
    def next_question(self, request):
        student = linked_student(request.user)
        try:
            session, question = practice.next_question(student)
        except PracticeError as error:
            return self._conflict(error)
        return Response(
            {
                "session_id": session.pk,
                "question_number": session.question_attempts.count() + 1,
                "session_length": settings.PRACTICE_SESSION_LENGTH,
                "question": PracticeQuestionSerializer(question).data,
            }
        )

    @action(detail=False, methods=["post"])
    def answer(self, request):
        serializer = PracticeAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = linked_student(request.user)
        try:
            result = practice.submit_answer(
                student, serializer.validated_data["answer_given"]
            )
        except PracticeError as error:
            return self._conflict(error)
        return Response(result)

    @action(detail=False, methods=["post"])
    def end(self, request):
        student = linked_student(request.user)
        try:
            session = practice.end_session(student)
        except PracticeError as error:
            return self._conflict(error)
        return Response(session_results(session))

    @action(detail=False, methods=["get"])
    def progress(self, request):
        """A student's home screen: grade, XP, level and streak."""
        student = linked_student(request.user)
        xp = xp_progress(student.total_xp)
        return Response(
            {
                "grade": student.grade,
                "total_xp": student.total_xp,
                "level": xp["level"],
                "xp_to_next_level": xp["xp_to_next_level"],
                "streak": streak_status(student),
            }
        )