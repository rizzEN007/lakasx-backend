from django.db.models import Q
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.exceptions import PermissionDenied

from .models import SchoolMembership, Student


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


def filter_to_user_schools(queryset, user, school_lookup, student_lookup=None):
    school_ids = managed_school_ids(user)

    if school_ids is None:
        return queryset

    condition = Q(**{f"{school_lookup}__in": school_ids})

    if student_lookup:
            student = linked_student(user)
            if student is not None:
                condition |= Q(**{student_lookup: student.pk})

    return queryset.filter(condition).distinct()


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

def linked_student(user):
    """The Student record this login is linked to, or None.

    Requires a live STUDENT membership in the student's school, so removing
    the membership ends the student's access.
    """
    if not (user and user.is_authenticated):
        return None
    student = Student.objects.filter(user=user).first()
    if student is None:
        return None
    has_membership = SchoolMembership.objects.filter(
        user=user,
        school_id=student.school_id,
        role=SchoolMembership.Role.STUDENT,
    ).exists()
    return student if has_membership else None

class IsStaffOrLinkedStudentReadOnly(BasePermission):
    """Staff get full access (get_queryset scopes by school).
    A linked student gets read-only access. Everyone else is denied."""

    message = "You do not have access to this school data."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser or SchoolMembership.objects.filter(
            user=user, role__in=STAFF_ROLES
        ).exists():
            return True
        return request.method in SAFE_METHODS and linked_student(user) is not None

class IsLinkedStudent(BasePermission):
    message = "Only a student account can practice."

    def has_permission(self, request, view):
        return linked_student(request.user) is not None