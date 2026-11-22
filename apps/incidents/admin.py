
from django.contrib import admin
from .models import Incident, IncidentStatusHistory, IncidentMedia


class IncidentMediaInline(admin.TabularInline):
    model = IncidentMedia
    extra = 0
    readonly_fields = ("uploaded_at",)
    fields = ("file", "media_type", "uploaded_by", "uploaded_at")


class IncidentStatusHistoryInline(admin.TabularInline):
    model = IncidentStatusHistory
    extra = 0
    readonly_fields = ("created_at",)
    fields = ("from_status", "to_status", "changed_by", "note", "created_at")


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "category",
        "reporter_display",
        "reporter_phone",
        "status",
        "source",
        "address_text",
        "created_at",
    )

    list_filter = (
        "status",
        "category",
        "source",
        "location_source",
        "created_at",
    )

    search_fields = (
        "reporter_name",
        "reporter_phone",
        "description",
        "address_text",
        "citizen__email",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "closed_at",
    )

    ordering = ("-created_at",)

    date_hierarchy = "created_at"

    list_per_page = 25

    inlines = (
        IncidentStatusHistoryInline,
        IncidentMediaInline,
    )

    fieldsets = (
        ("Incident Information", {
            "fields": (
                "citizen",
                "reporter_name",
                "reporter_phone",
                "source",
                "category",
                "description",
                "status",
            )
        }),
        ("Location Information", {
            "fields": (
                "address_text",
                "latitude",
                "longitude",
                "location_source",
                "location_accuracy_m",
                "location_captured_at",
            )
        }),
        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
                "closed_at",
            )
        }),
    )


@admin.register(IncidentStatusHistory)
class IncidentStatusHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "incident",
        "from_status",
        "to_status",
        "changed_by",
        "created_at",
    )

    list_filter = ("from_status", "to_status", "created_at")

    search_fields = (
        "incident__id",
        "note",
    )

    readonly_fields = ("created_at",)

    ordering = ("-created_at",)


@admin.register(IncidentMedia)
class IncidentMediaAdmin(admin.ModelAdmin):
    list_display = (
        "incident",
        "media_type",
        "uploaded_by",
        "uploaded_at",
    )

    list_filter = ("media_type", "uploaded_at")

    search_fields = ("incident__id",)

    readonly_fields = ("uploaded_at",)
