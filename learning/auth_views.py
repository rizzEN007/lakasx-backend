
from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .access import linked_student,guardian_links
from .serializers_auth import RegisterSerializer

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .services import lockout

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

    def post(self, request, *args, **kwargs):
        data = request.data
        identifier = data.get("username", "") if hasattr(data, "get") else ""

        remaining = lockout.seconds_locked(identifier)
        if remaining:
            return Response(
                {"detail": "Too many failed attempts. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(remaining)},
            )

        try:
            response = super().post(request, *args, **kwargs)
        except AuthenticationFailed:
            lockout.register_failure(identifier)
            raise

        lockout.clear_failures(identifier)
        return response

class LogoutView(APIView):
    """Blacklist a refresh token. Possessing the token is the credential."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = request.data
        refresh = data.get("refresh") if hasattr(data, "get") else None
        if not isinstance(refresh, str) or not refresh:
            return Response(
                {"detail": "A refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            return Response(
                {"detail": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)