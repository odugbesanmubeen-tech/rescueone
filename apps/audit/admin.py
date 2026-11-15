import json
from django.contrib import admin
from django.utils.html import format_html
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "target_type", "target_id", "ip_address")
    list_filter = ("action", "target_type", "created_at")
    search_fields = ("target_id", "ip_address", "user__username", "user__email")
    list_select_related = ("user",)
    date_hierarchy = "created_at"
    
    readonly_fields = [f.name for f in AuditLog._meta.fields if f.name != "details"] + ["formatted_details"]
    exclude = ("details",)

    @admin.display(description="Details")
    def formatted_details(self, obj):
        pretty_json = json.dumps(obj.details, indent=2)
        return format_html("<pre style='margin: 0;'>{}</pre>", pretty_json)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
