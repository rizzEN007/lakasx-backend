import math
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from learning.models import Classroom, PracticeSession, School, Student

from .access import portal_required, scoped

# The account-lock feature is optional: the portal works without it.
try:
    from learning.models import LoginAttempt
    from learning.services import lockout
except ImportError:  # lock not installed yet
    LoginAttempt = None
    lockout = None


class PortalLoginView(LoginView):
    template_name = "portal/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        if lockout is not None:
            remaining = lockout.seconds_locked(request.POST.get("username", ""))
            if remaining:
                context = self.get_context_data(form=self.form_class(request=request))
                context["locked_message"] = (
                    "Too many failed attempts. Try again in "
                    f"{math.ceil(remaining / 60)} minute(s)."
                )
                response = self.render_to_response(context)
                response.status_code = 429
                return response
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        if lockout is not None:
            lockout.register_failure(self.request.POST.get("username", ""))
        return super().form_invalid(form)

    def form_valid(self, form):
        if lockout is not None:
            lockout.clear_failures(form.get_user().get_username())
        return super().form_valid(form)


@portal_required
def dashboard(request):
    students = scoped(Student.objects.all(), request)
    since = timezone.now() - timedelta(days=7)
    sessions = PracticeSession.objects.filter(student__in=students)
    context = {
        "school_count": scoped(School.objects.all(), request, field="id").count(),
        "student_count": students.count(),
        "classroom_count": scoped(Classroom.objects.all(), request).count(),
        "sessions_7d": sessions.filter(started_at__gte=since).count(),
        "recent": sessions.select_related("student").order_by("-started_at")[:10],
    }
    return render(request, "portal/dashboard.html", context)


@portal_required
def students(request):
    qs = (
        scoped(Student.objects.select_related("school", "user"), request)
        .annotate(session_count=Count("practice_sessions"))
        .order_by("name")
    )
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q))
    school = request.GET.get("school", "")
    if school.isdigit():
        qs = qs.filter(school_id=int(school))

    params = request.GET.copy()
    params.pop("page", None)
    context = {
        "page": Paginator(qs, 25).get_page(request.GET.get("page")),
        "schools": scoped(School.objects.order_by("name"), request, field="id"),
        "q": q,
        "school": school,
        "extra": params.urlencode(),
    }
    return render(request, "portal/students.html", context)


@portal_required
def student_detail(request, pk):
    student = get_object_or_404(
        scoped(Student.objects.select_related("school", "user"), request), pk=pk
    )
    context = {
        "student": student,
        "guardians": student.guardian_links.select_related("user"),
        "sessions": student.practice_sessions.order_by("-started_at")[:10],
    }
    return render(request, "portal/student_detail.html", context)


@portal_required
def classrooms(request):
    qs = (
        scoped(Classroom.objects.select_related("school"), request)
        .annotate(
            student_count=Count("students", distinct=True),
            teacher_count=Count("teachers", distinct=True),
        )
        .order_by("school__name", "name")
    )
    return render(request, "portal/classrooms.html", {"classrooms": qs})


@portal_required
def locked_accounts(request):
    if LoginAttempt is None:
        raise Http404
    if not request.user.is_superuser:
        return render(request, "portal/no_access.html", status=403)

    if request.method == "POST":
        pk = request.POST.get("id", "")
        if pk.isdigit():
            LoginAttempt.objects.filter(pk=int(pk)).delete()
            messages.success(request, "Account unlocked.")
        return redirect("portal:locked")

    locked = LoginAttempt.objects.filter(locked_until__gt=timezone.now()).order_by(
        "-locked_until"
    )
    return render(request, "portal/locked.html", {"locked": locked})
