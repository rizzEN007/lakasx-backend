
from django.contrib.auth import get_user_model
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from .access import linked_student,guardian_links
from .serializers_auth import RegisterSerializer

from rest_framework_simplejwt.views import TokenObtainPairView

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "registration"


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        memberships = request.user.school_memberships.select_related(
            "school"
        ).all()

        student = linked_student(request.user)

        return Response({
            "id": request.user.id,
            "username": request.user.username,
            "email": request.user.email,
            "student_id": student.id if student else None,
            "children": [
                {
                    "student_id": link.student_id,
                    "name": link.student.name,
                    "relationship": link.relationship,
                }
                for link in guardian_links(request.user)
            ],
            "memberships": [
                {
                    "school_id": membership.school_id,
                    "school_name": membership.school.name,
                    "role": membership.role,
                }
                for membership in memberships
            ],
        })
    
class LoginView(TokenObtainPairView):
    throttle_scope = "login"