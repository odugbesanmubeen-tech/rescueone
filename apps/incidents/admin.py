from django.contrib import admin
from .models import Incident


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "created_at",
    )

    list_filter = ("status",)

    search_fields = ("id",)

    ordering = ("-id",)