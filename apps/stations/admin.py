from django.contrib import admin

from .models import Station


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "address", "has_coordinates", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "address", "phone")
    readonly_fields = ("created_at",)
    actions = ["activate_stations", "deactivate_stations"]

    fieldsets = (
        ("Station Information", {"fields": ("name", "phone", "address", "is_active")}),
        ("Coordinates", {"fields": ("latitude", "longitude")}),
        ("Metadata", {"fields": ("created_at",)}),
    )

    @admin.display(boolean=True, description="Has GPS")
    def has_coordinates(self, obj):
        return obj.has_location

    @admin.action(description="Activate selected stations")
    def activate_stations(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Deactivate selected stations")
    def deactivate_stations(self, request, queryset):
        queryset.update(is_active=False)
