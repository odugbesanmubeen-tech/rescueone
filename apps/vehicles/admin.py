from django.contrib import admin

from .models import Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("number", "vehicle_type", "station", "is_available", "created_at")
    list_filter = ("is_available", "vehicle_type", "station")
    search_fields = ("number", "station__name")
    list_select_related = ("station",)
    raw_id_fields = ("station",)
    readonly_fields = ("created_at",)
    actions = ["mark_available", "mark_unavailable"]

    fieldsets = (
        ("Vehicle Details", {"fields": ("number", "vehicle_type", "station", "is_available")}),
        ("Metadata", {"fields": ("created_at",)}),
    )

    @admin.action(description="Mark selected vehicles as available")
    def mark_available(self, request, queryset):
        queryset.update(is_available=True)

    @admin.action(description="Mark selected vehicles as unavailable")
    def mark_unavailable(self, request, queryset):
        queryset.update(is_available=False)
