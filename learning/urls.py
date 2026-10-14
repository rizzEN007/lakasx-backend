from django.urls import include, path
from rest_framework.routers import DefaultRouter


from rest_framework_simplejwt.views import (
       TokenRefreshView,
)

from .auth_views import RegisterView, MeView, LoginView

from .views import(
    ParentChildViewSet,
    PracticeViewSet,
    StudentViewSet, 
    PracticeSessionViewSet, 
    QuestionViewSet, 
    QuestionAttemptViewSet,
    LevelViewSet,
    TopicViewSet, 
    PlacementAssessmentViewSet,
    PlacementAttemptViewSet, 
    )

from .school_views import (
    SchoolListView,
    SchoolMemberListCreateView,
    SchoolMemberDetailView,
)

router = DefaultRouter()

router.register("students", StudentViewSet)
router.register("levels", LevelViewSet)
router.register("topics", TopicViewSet)
router.register("practice-sessions", PracticeSessionViewSet)
router.register("questions", QuestionViewSet)
router.register("question-attempts", QuestionAttemptViewSet)
router.register("placement-assessments", PlacementAssessmentViewSet)
router.register("placement-attempts", PlacementAttemptViewSet)
router.register("practice", PracticeViewSet, basename="practice")
router.register("parent/children", ParentChildViewSet, basename="parent-child")

urlpatterns = [
    path(
        "auth/register/",
          RegisterView.as_view(),
          name="register"
    ),

    path(
        "auth/login/",
        LoginView.as_view(),
        name="token_obtain_pair",
    ),

    path(
        "auth/token/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),

    path(
        "auth/me/", 
        MeView.as_view(), 
        name="me"
    ),

    path(
        "schools/", 
        SchoolListView.as_view(), 
        name="school-list"
    ),

    path(
        "schools/<int:school_id>/members/",
        SchoolMemberListCreateView.as_view(),
        name="school-members",
    ),
    path(
        "schools/<int:school_id>/members/<int:membership_id>/",
        SchoolMemberDetailView.as_view(),
        name="school-member-detail",
    ),
    path(
        "", 
        include(router.urls)
    ),
]
