from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", views.PortalLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="portal:login"), name="logout"),
    path("students/", views.students, name="students"),
    path("students/<int:pk>/", views.student_detail, name="student_detail"),
    path("classrooms/", views.classrooms, name="classrooms"),
    path("locked/", views.locked_accounts, name="locked"),
]
