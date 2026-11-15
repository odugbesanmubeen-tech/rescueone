from django.contrib import admin

from .models import Availability, ResponderProfile


@admin.register(ResponderProfile)
class ResponderProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "responder_type",
        "availability",
        "station",
        "vehicle",
        "has_fresh_location",
        "last_location_at",
    )
    list_filter = ("availability", "responder_type", "station")
    search_fields = (
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "station__name",
        "vehicle__plate_number",
    )
    list_select_related = ("user", "station", "vehicle")
    raw_id_fields = ("user", "station", "vehicle")
    readonly_fields = (
        "last_latitude",
        "last_longitude",
        "last_location_accuracy_m",
        "last_location_at",
        "location_is_stale",
    )
    actions = ["set_online", "set_offline"]

    fieldsets = (
        ("Responder Details", {"fields": ("user", "responder_type", "availability")}),
        ("Assignments", {"fields": ("station", "vehicle")}),
        (
            "Latest GPS Position",
            {
                "fields": (
                    "last_latitude",
                    "last_longitude",
                    "last_location_accuracy_m",
                    "last_location_at",
                    "location_is_stale",
                )
            },
        ),
    )

    @admin.display(boolean=True, description="Fresh GPS")
    def has_fresh_location(self, obj):
        return obj.has_location and not obj.location_is_stale

    @admin.action(description="Set selected responders to Online")
    def set_online(self, request, queryset):
        queryset.update(availability=Availability.ONLINE)

    @admin.action(description="Set selected responders to Offline")
    def set_offline(self, request, queryset):
        queryset.update(availability=Availability.OFFLINE)

