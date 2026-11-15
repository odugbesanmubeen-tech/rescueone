from django.contrib import admin

from .models import Incident, IncidentMedia, IncidentStatusHistory


class IncidentStatusHistoryInline(admin.TabularInline):
    model = IncidentStatusHistory
    extra = 0
    fields = ("created_at", "from_status", "to_status", "changed_by", "note")
    readonly_fields = ("created_at", "from_status", "to_status", "changed_by", "note")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class IncidentMediaInline(admin.TabularInline):
    model = IncidentMedia
    extra = 0
    fields = ("file", "media_type", "uploaded_by", "uploaded_at")
    readonly_fields = ("uploaded_at",)
    raw_id_fields = ("uploaded_by",)


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "category",
        "status",
        "source",
        "reporter_display",
        "reporter_phone",
        "address_text",
        "created_at",
        "closed_at",
    )
    list_filter = ("status", "category", "source", "location_source", "created_at")
    search_fields = (
        "id",
        "reporter_name",
        "reporter_phone",
        "address_text",
        "description",
        "citizen__username",
        "citizen__email",
    )
    list_select_related = ("citizen",)
    raw_id_fields = ("citizen",)
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    inlines = [IncidentStatusHistoryInline, IncidentMediaInline]

    fieldsets = (
        ("Incident Overview", {"fields": ("category", "status", "source", "description")}),
        ("Reporter Details", {"fields": ("citizen", "reporter_name", "reporter_phone")}),
        (
            "Location Data",
            {
                "fields": (
                    "address_text",
                    "latitude",
                    "longitude",
                    "location_source",
                    "location_accuracy_m",
                    "location_captured_at",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at", "closed_at")}),
    )


@admin.register(IncidentStatusHistory)
class IncidentStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "incident", "from_status", "to_status", "changed_by", "note")
    list_filter = ("to_status", "from_status", "created_at")
    search_fields = ("incident__id", "note", "changed_by__username")
    list_select_related = ("incident", "changed_by")
    raw_id_fields = ("incident", "changed_by")
    readonly_fields = [f.name for f in IncidentStatusHistory._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IncidentMedia)
class IncidentMediaAdmin(admin.ModelAdmin):
    list_display = ("id", "incident", "media_type", "file", "uploaded_by", "uploaded_at")
    list_filter = ("media_type", "uploaded_at")
    search_fields = ("incident__id", "uploaded_by__username")
    list_select_related = ("incident", "uploaded_by")
    raw_id_fields = ("incident", "uploaded_by")
    readonly_fields = ("uploaded_at",)
