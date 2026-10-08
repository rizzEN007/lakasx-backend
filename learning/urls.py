from rest_framework.routers import DefaultRouter
from .views import StudentViewSet, PracticeSessionViewSet, QuestionViewSet

router = DefaultRouter()

router.register("students", StudentViewSet)
router.register("practice-sessions", PracticeSessionViewSet)
router.register("questions", QuestionViewSet)

urlpatterns = router.urls