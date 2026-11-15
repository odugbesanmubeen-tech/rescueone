from django.contrib import admin

from .models import DispatcherProfile, IncidentAssignment


@admin.register(DispatcherProfile)
class DispatcherProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "employee_id", "station")
    list_filter = ("station",)
    search_fields = ("employee_id", "user__username", "user__email", "user__first_name", "user__last_name")
    list_select_related = ("user", "station")
    raw_id_fields = ("user",)


@admin.register(IncidentAssignment)
class IncidentAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "incident",
        "responder",
        "vehicle",
        "status",
        "assigned_by",
        "offered_at",
        "responded_at",
        "closed_at",
    )
    list_filter = ("status", "offered_at", "responded_at", "closed_at")
    search_fields = (
        "incident__id",
        "responder__user__username",
        "responder__user__email",
        "assigned_by__username",
    )
    list_select_related = ("incident", "responder", "responder__user", "vehicle", "assigned_by")
    raw_id_fields = ("incident", "responder", "vehicle", "assigned_by")
    readonly_fields = ("offered_at",)
    date_hierarchy = "offered_at"
