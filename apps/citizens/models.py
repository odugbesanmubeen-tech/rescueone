from django.conf import settings
from django.db import models


class CitizenProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="citizen_profile")
    address = models.CharField(max_length=255, blank=True)
    emergency_contact_name = models.CharField(max_length=120, blank=True)
    emergency_contact_phone = models.CharField(max_length=32, blank=True)

    def __str__(self):
        return f"Citizen: {self.user}"
