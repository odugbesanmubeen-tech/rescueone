from django.contrib import admin
from .models import CitizenProfile

@admin.register(CitizenProfile)
class CitizenProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "address", "emergency_contact_name", "emergency_contact_phone")
    search_fields = (
        "user__email", 
        "user__first_name", 
        "user__last_name", 
        "address", 
        "emergency_contact_name", 
        "emergency_contact_phone"
    )
    raw_id_fields = ("user",)
