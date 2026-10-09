from django.contrib import admin
from .models import School, SchoolMembership, Classroom


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "contact_email", "created_at")
    search_fields = ("name", "code", "contact_email")


@admin.register(SchoolMembership)
class SchoolMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "school", "role", "created_at")
    list_filter = ("role", "school")
    search_fields = (
        "user__username",
        "user__email",
        "school__name",
    )

@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ("name", "school", "grade_level", "academic_year")
    list_filter = ("school", "academic_year", "grade_level")
    search_fields = ("name", "school__name")