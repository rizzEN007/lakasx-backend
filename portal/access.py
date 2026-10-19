from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from learning.models import SchoolMembership

STAFF_ROLES = (SchoolMembership.Role.ADMIN, SchoolMembership.Role.TEACHER)


def school_ids_for(user):
    """None means 'every school' (superuser). Otherwise a list of school ids."""
    if user.is_superuser:
        return None
    return list(
        SchoolMembership.objects.filter(user=user, role__in=STAFF_ROLES)
        .values_list("school_id", flat=True)
    )


def portal_required(view):
    """Must be logged in AND be a superuser or an ADMIN/TEACHER of some school."""

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        ids = school_ids_for(request.user)
        if ids is not None and not ids:
            return render(request, "portal/no_access.html", status=403)
        request.school_ids = ids
        return view(request, *args, **kwargs)

    return wrapper


def scoped(queryset, request, field="school_id"):
    """Limit a queryset to the schools this user may see."""
    if request.school_ids is None:
        return queryset
    return queryset.filter(**{f"{field}__in": request.school_ids})
