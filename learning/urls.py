from rest_framework.routers import DefaultRouter
from .views import(
    StudentViewSet, 
    PracticeSessionViewSet, 
    QuestionViewSet, 
    QuestionAttemptViewSet,
    LevelViewSet,
    TopicViewSet, 
    PlacementAssessmentViewSet,
    PlacementAttemptViewSet, 
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

urlpatterns = router.urls