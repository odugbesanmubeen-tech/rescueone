from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class ResponderType(models.TextChoices):
    FIREFIGHTER = "FIREFIGHTER", "Firefighter"
    AMBULANCE = "AMBULANCE", "Ambulance personnel"
    SECURITY = "SECURITY", "Security personnel"
    OTHER = "OTHER", "Other"


class Availability(models.TextChoices):
    OFFLINE = "OFFLINE", "Offline"
    ONLINE = "ONLINE", "Online"
    BUSY = "BUSY", "Busy"


class ResponderProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="responder_profile")
    responder_type = models.CharField(max_length=16, choices=ResponderType.choices, default=ResponderType.OTHER)
    station = models.ForeignKey(
        "stations.Station", null=True, blank=True, on_delete=models.SET_NULL, related_name="responders"
    )
    vehicle = models.ForeignKey(
        "vehicles.Vehicle", null=True, blank=True, on_delete=models.SET_NULL, related_name="responders"
    )
    availability = models.CharField(
        max_length=8, choices=Availability.choices, default=Availability.OFFLINE, db_index=True
    )
    # Latest reported position (denormalised from locations.ResponderLocation).
    last_latitude = models.FloatField(null=True, blank=True)
    last_longitude = models.FloatField(null=True, blank=True)
    last_location_accuracy_m = models.FloatField(null=True, blank=True)
    last_location_at = models.DateTimeField(null=True, blank=True)

    @property
    def has_location(self):
        return self.last_latitude is not None and self.last_longitude is not None

    @property
    def lat(self):
        return self.last_latitude

    @property
    def lng(self):
        return self.last_longitude

    @property
    def location_is_stale(self):
        if not self.last_location_at:
            return True
        limit = timedelta(minutes=settings.STALE_LOCATION_MINUTES)
        return timezone.now() - self.last_location_at > limit

    def __str__(self):
        return f"Responder: {self.user}"
