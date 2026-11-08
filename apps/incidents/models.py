from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class Status(models.TextChoices):
    REPORTED = "REPORTED", "Reported"
    DISPATCH_PENDING = "DISPATCH_PENDING", "Dispatch pending"
    ASSIGNED = "ASSIGNED", "Assigned"
    EN_ROUTE = "EN_ROUTE", "En route"
    ON_SCENE = "ON_SCENE", "On scene"
    RESOLVED = "RESOLVED", "Resolved"
    CANCELLED = "CANCELLED", "Cancelled"
    FALSE_ALARM = "FALSE_ALARM", "False alarm"


class Category(models.TextChoices):
    MEDICAL = "MEDICAL", "Medical"
    FIRE = "FIRE", "Fire"
    CRIME = "CRIME", "Crime / security"
    ACCIDENT = "ACCIDENT", "Accident"
    OTHER = "OTHER", "Other"


class Source(models.TextChoices):
    CITIZEN_APP = "CITIZEN_APP", "Citizen app"
    DISPATCHER = "DISPATCHER", "Logged by dispatcher"


class LocationSource(models.TextChoices):
    GPS = "GPS", "Device GPS"
    MANUAL = "MANUAL", "Entered manually"


ACTIVE_STATUSES = [Status.REPORTED, Status.DISPATCH_PENDING, Status.ASSIGNED, Status.EN_ROUTE, Status.ON_SCENE]
TERMINAL_STATUSES = [Status.RESOLVED, Status.CANCELLED, Status.FALSE_ALARM]


class Incident(models.Model):
    citizen = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="incidents"
    )
    reporter_name = models.CharField(max_length=120, blank=True)
    reporter_phone = models.CharField(max_length=32, blank=True)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.CITIZEN_APP)
    category = models.CharField(max_length=16, choices=Category.choices, default=Category.OTHER, db_index=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REPORTED, db_index=True)

    latitude = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    location_source = models.CharField(max_length=8, choices=LocationSource.choices, blank=True)
    location_accuracy_m = models.FloatField(null=True, blank=True)
    location_captured_at = models.DateTimeField(null=True, blank=True)
    address_text = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]
        constraints = [
            models.CheckConstraint(
                condition=(Q(latitude__isnull=False) & Q(longitude__isnull=False)) | ~Q(address_text=""),
                name="incident_has_location_or_address",
            )
        ]

    @property
    def has_location(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def lat(self):
        return self.latitude

    @property
    def lng(self):
        return self.longitude

    @property
    def is_active(self):
        return self.status in ACTIVE_STATUSES

    @property
    def reporter_display(self):
        if self.citizen_id:
            return self.citizen.display_name
        return self.reporter_name or "Unknown caller"

    def __str__(self):
        return f"Incident #{self.pk} ({self.status})"


class IncidentStatusHistory(models.Model):
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=20, choices=Status.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=Status.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class IncidentMedia(models.Model):
    class MediaType(models.TextChoices):
        PHOTO = "PHOTO", "Photo"
        VIDEO = "VIDEO", "Video"
        AUDIO = "AUDIO", "Voice recording"

    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="media")
    file = models.FileField(upload_to="incidents/%Y/%m/")
    media_type = models.CharField(max_length=8, choices=MediaType.choices)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
