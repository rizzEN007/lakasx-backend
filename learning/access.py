from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.exceptions import PermissionDenied

from .models import SchoolMembership


STAFF_ROLES = (
    SchoolMembership.Role.ADMIN,
    SchoolMembership.Role.TEACHER,
)


def managed_school_ids(user):
    """Return schools the user can manage, or None for a platform superuser."""
    if user.is_superuser:
        return None

    return SchoolMembership.objects.filter(
        user=user,
        role__in=STAFF_ROLES,
    ).values_list("school_id", flat=True)


def can_access_school(user, school_id):
    if user.is_superuser:
        return True

    return SchoolMembership.objects.filter(
        user=user,
        school_id=school_id,
        role__in=STAFF_ROLES,
    ).exists()


def filter_to_user_schools(queryset, user, school_lookup):
    school_ids = managed_school_ids(user)

    if school_ids is None:
        return queryset

    return queryset.filter(
        **{f"{school_lookup}__in": school_ids}
    ).distinct()


class IsPlatformSuperuserOrReadOnly(BasePermission):
    """Authenticated users may read shared curriculum; only superusers edit it."""

    def has_permission(self, request, view):
        return (
            request.method in SAFE_METHODS
            or bool(request.user and request.user.is_superuser)
        )

def is_school_admin(user, school_id):
    if user.is_superuser:
        return True
    return SchoolMembership.objects.filter(
        user=user, school_id=school_id, role=SchoolMembership.Role.ADMIN
    ).exists()
class IsSchoolStaff(BasePermission):
    message = "You are not a staff member of any school."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return user.is_superuser or SchoolMembership.objects.filter(
            user=user, role__in=STAFF_ROLES
        ).exists()


class IsSchoolMember(BasePermission):
    message = "You do not belong to any school."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return user.is_superuser or SchoolMembership.objects.filter(
            user=user
        ).exists()


class AdminOnlyDeleteMixin:
    """Deleting cascades to history, so only a school admin may do it."""

    def school_id_of(self, instance):
        raise NotImplementedError

    def perform_destroy(self, instance):
        if not is_school_admin(self.request.user, self.school_id_of(instance)):
            raise PermissionDenied("Only a school administrator can delete this.")
        super().perform_destroy(instance)