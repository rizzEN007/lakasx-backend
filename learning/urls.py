from rest_framework.routers import DefaultRouter
from .views import StudentViewSet

router = DefaultRouter()
router.register("students", StudentViewSet)

urlpatterns = router.urls

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("learning.urls")),
]