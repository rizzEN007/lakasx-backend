
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import School, SchoolMembership
from .school_serializers import AddSchoolMemberSerializer

User = get_user_model()


def can_manage_school(user, school):
    if user.is_superuser:
        return True

    return SchoolMembership.objects.filter(
        school=school,
        user=user,
        role=SchoolMembership.Role.ADMIN,
    ).exists()


def membership_data(membership):
    return {
        "id": membership.id,
        "user_id": membership.user_id,
        "username": membership.user.username,
        "email": membership.user.email,
        "school_id": membership.school_id,
        "role": membership.role,
        "created_at": membership.created_at,
    }


class SchoolListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_superuser:
            schools = School.objects.all().order_by("name")
            return Response([
                {
                    "id": school.id,
                    "name": school.name,
                    "code": school.code,
                    "role": "PLATFORM_SUPERUSER",
                }
                for school in schools
            ])

        memberships = (
            SchoolMembership.objects
            .filter(user=request.user)
            .select_related("school")
            .order_by("school__name")
        )

        return Response([
            {
                "id": membership.school_id,
                "name": membership.school.name,
                "code": membership.school.code,
                "role": membership.role,
            }
            for membership in memberships
        ])


class SchoolMemberListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get_school(self, school_id):
        return get_object_or_404(School, pk=school_id)

    def get(self, request, school_id):
        school = self.get_school(school_id)

        if not can_manage_school(request.user, school):
            return Response(
                {"detail": "You cannot manage this school's members."},
                status=status.HTTP_403_FORBIDDEN,
            )

        memberships = (
            SchoolMembership.objects
            .filter(school=school)
            .select_related("user", "school")
            .order_by("id")
        )

        return Response([
            membership_data(membership)
            for membership in memberships
        ])

    def post(self, request, school_id):
        school = self.get_school(school_id)

        if not can_manage_school(request.user, school):
            return Response(
                {"detail": "You cannot manage this school's members."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AddSchoolMemberSerializer(
            data=request.data,
            context={
                "request": request,
                "school": school,
            },
        )
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                membership = SchoolMembership.objects.create(
                    school=school,
                    user=serializer.validated_data["user"],
                    role=serializer.validated_data["role"],
                )
        except IntegrityError:
            return Response(
                {"detail": "This user may already belong to this school."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "id": membership.id,
                "school_id": school.id,
                "role": membership.role,
                "created_at": membership.created_at,
            },
            status=status.HTTP_201_CREATED,
        )


class SchoolMemberDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, school_id, membership_id):
        school = get_object_or_404(School, pk=school_id)

        if not can_manage_school(request.user, school):
            return Response(
                {"detail": "You cannot manage this school's members."},
                status=status.HTTP_403_FORBIDDEN,
            )

        membership = get_object_or_404(
            SchoolMembership.objects.select_related("user"),
            pk=membership_id,
            school=school,
        )

        # School admins cannot remove an administrator.
        # A platform superuser can do so.
        if (
            membership.role == SchoolMembership.Role.ADMIN
            and not request.user.is_superuser
        ):
            return Response(
                {"detail": "Only a platform superuser can remove "
                           "a school administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )

        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)