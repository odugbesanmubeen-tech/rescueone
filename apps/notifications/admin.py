from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "kind", "short_message", "incident", "is_read", "created_at")
    list_filter = ("is_read", "kind", "created_at")
    search_fields = ("message", "user__username", "user__email", "incident__id")
    list_select_related = ("user", "incident")
    raw_id_fields = ("user", "incident")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
    actions = ["mark_as_read", "mark_as_unread"]

    @admin.display(description="Message")
    def short_message(self, obj):
        return obj.message if len(obj.message) <= 60 else f"{obj.message[:57]}..."

    @admin.action(description="Mark selected notifications as read")
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)

    @admin.action(description="Mark selected notifications as unread")
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)
