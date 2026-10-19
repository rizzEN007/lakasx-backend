from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response

from .services.streaks import streak_status
from .services.xp import xp_progress

from django.db import IntegrityError
from django.shortcuts import get_object_or_404

from .access import (
    AdminOnlyDeleteMixin,
    IsLinkedStudent,
    IsParentGuardian,
    IsPlatformSuperuserOrReadOnly,
    IsSchoolMember,
    IsSchoolStaff,
    IsStaffOrFamilyReadOnly,
    filter_to_user_schools,
    guardian_links,
    is_school_admin,
    linked_student,
)
from .services import practice, reports
from .services import store as store_service
from .services.practice import PracticeError, session_results, settings
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
    GuardianLink,
    StoreItem,
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
    AddGuardianSerializer,
    StoreItemSerializer,
    StoreItemRequestSerializer,
)


class AppendOnlyViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Attempts are a record of what happened: create and read only."""

def guardian_data(link):
    return {
        "id": link.id,
        "user_id": link.user_id,
        "email": link.user.email,
        "relationship": link.relationship,
        "created_at": link.created_at,
    }

class StudentViewSet(AdminOnlyDeleteMixin, viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated, IsStaffOrFamilyReadOnly]

    def school_id_of(self, instance):
        return instance.school_id

    def get_queryset(self):
        return filter_to_user_schools(
            super().get_queryset(),
            self.request.user,
            "school_id",
            "pk",
            include_family=self.request.method in SAFE_METHODS,
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

    @action(detail=True, methods=["get"], url_path="guardians")

    def guardians(self, request, pk=None):
        student = self.get_object()
        self._require_admin(student)
        links = student.guardian_links.select_related("user").order_by("id")
        return Response([guardian_data(link) for link in links])

    @guardians.mapping.post
    def add_guardian(self, request, pk=None):
        student = self.get_object()
        self._require_admin(student)
        serializer = AddGuardianSerializer(
            data=request.data, context={"student": student}
        )
        serializer.is_valid(raise_exception=True)
        try:
            link = GuardianLink.objects.create(
                student=student,
                user=serializer.validated_data["user"],
                relationship=serializer.validated_data["relationship"],
            )
        except IntegrityError:
            return Response(
                {"detail": "This guardian could not be added."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(guardian_data(link), status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"guardians/(?P<link_id>[0-9]+)",
    )
    def remove_guardian(self, request, pk=None, link_id=None):
        student = self.get_object()
        self._require_admin(student)
        link = get_object_or_404(GuardianLink, pk=link_id, student=student)
        link.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


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
    permission_classes = [IsAuthenticated, IsStaffOrFamilyReadOnly]

    def school_id_of(self, instance):
        return instance.student.school_id

    def get_queryset(self):
        return filter_to_user_schools(
            super().get_queryset(),
            self.request.user,
            "student__school_id",
            "student_id",
            include_family=self.request.method in SAFE_METHODS,
        )

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        return Response(session_results(self.get_object()))


class QuestionAttemptViewSet(AppendOnlyViewSet):
    queryset = QuestionAttempt.objects.all()
    serializer_class = QuestionAttemptSerializer
    permission_classes = [IsAuthenticated, IsStaffOrFamilyReadOnly]

    def get_queryset(self):
        return filter_to_user_schools(
            super().get_queryset(),
            self.request.user,
            "practice_session__student__school_id",
            "practice_session__student_id",            
            include_family=self.request.method in SAFE_METHODS,
        )


class PlacementAssessmentViewSet(AdminOnlyDeleteMixin, viewsets.ModelViewSet):
    queryset = PlacementAssessment.objects.all()
    serializer_class = PlacementAssessmentSerializer
    permission_classes = [IsAuthenticated, IsStaffOrFamilyReadOnly]

    def school_id_of(self, instance):
        return instance.student.school_id

    def get_queryset(self):
        return filter_to_user_schools(
            super().get_queryset(),
            self.request.user,
            "student__school_id",
            "student_id",           
            include_family=self.request.method in SAFE_METHODS,
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
    permission_classes = [IsAuthenticated, IsStaffOrFamilyReadOnly]

    def get_queryset(self):
        return filter_to_user_schools(
            super().get_queryset(),
            self.request.user,
            "assessment__student__school_id",
            "assessment__student_id",            
            include_family=self.request.method in SAFE_METHODS,
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

class ParentChildViewSet(viewsets.ViewSet):
    """A parent's view of their own children. Read-only."""

    permission_classes = [IsAuthenticated, IsParentGuardian]
    lookup_value_regex = "[0-9]+"

    def _links(self, request):
        return guardian_links(request.user)

    def list(self, request):
        links = self._links(request).order_by("student__name")
        return Response(
            [reports.child_summary(l.student, l.relationship) for l in links]
        )

    def retrieve(self, request, pk=None):
        link = get_object_or_404(self._links(request), student_id=pk)
        return Response(reports.child_summary(link.student, link.relationship))

    @action(detail=True, methods=["get"], url_path="weekly-summary")
    def weekly_summary(self, request, pk=None):
        link = get_object_or_404(self._links(request), student_id=pk)
        return Response(reports.weekly_summary(link.student))

class StoreItemViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """The shop catalog. Any member reads it; only a superuser changes it.

    There is no DELETE: retire an item with is_active=false, because students may own it.
    """

    queryset = StoreItem.objects.all().order_by("slot", "price", "id")
    serializer_class = StoreItemSerializer
    permission_classes = [
        IsAuthenticated,
        IsSchoolMember,
        IsPlatformSuperuserOrReadOnly,
    ]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(is_active=True)


class StoreViewSet(viewsets.ViewSet):
    """A student's wallet, shop and avatar inventory."""

    permission_classes = [IsAuthenticated, IsLinkedStudent]

    @staticmethod
    def _error(error):
        http = (
            status.HTTP_404_NOT_FOUND
            if error.code == "ITEM_NOT_FOUND"
            else status.HTTP_409_CONFLICT
        )
        return Response({"code": error.code, "detail": error.message}, status=http)

    @action(detail=False, methods=["get"])
    def wallet(self, request):
        return Response(store_service.wallet(linked_student(request.user)))

    @action(detail=False, methods=["get"])
    def shop(self, request):
        return Response(store_service.shop(linked_student(request.user)))

    @action(detail=False, methods=["get"])
    def inventory(self, request):
        return Response(store_service.inventory(linked_student(request.user)))

    def _change(self, request, operation, success_status):
        serializer = StoreItemRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = linked_student(request.user)
        try:
            owned = operation(student, serializer.validated_data["item_id"])
        except store_service.StoreError as error:
            return self._error(error)
        body = store_service.entry(owned)
        body["balance"] = student.coin_balance
        return Response(body, status=success_status)

    @action(detail=False, methods=["post"])
    def buy(self, request):
        return self._change(request, store_service.buy_item, status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def equip(self, request):
        return self._change(request, store_service.equip_item, status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    def unequip(self, request):
        return self._change(request, store_service.unequip_item, status.HTTP_200_OK)