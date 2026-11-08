from django.conf import settings
from django.db import models
from django.db.models import Q


class DispatcherProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dispatcher_profile")
    employee_id = models.CharField(max_length=32, blank=True)
    station = models.ForeignKey(
        "stations.Station", null=True, blank=True, on_delete=models.SET_NULL, related_name="dispatchers"
    )

    def __str__(self):
        return f"Dispatcher: {self.user}"


class AssignmentStatus(models.TextChoices):
    OFFERED = "OFFERED", "Offered"
    ACCEPTED = "ACCEPTED", "Accepted"
    DECLINED = "DECLINED", "Declined"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"


ACTIVE_ASSIGNMENT_STATUSES = [AssignmentStatus.OFFERED, AssignmentStatus.ACCEPTED]


class IncidentAssignment(models.Model):
    incident = models.ForeignKey("incidents.Incident", on_delete=models.CASCADE, related_name="assignments")
    responder = models.ForeignKey("responders.ResponderProfile", on_delete=models.CASCADE, related_name="assignments")
    vehicle = models.ForeignKey("vehicles.Vehicle", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(
        max_length=10, choices=AssignmentStatus.choices, default=AssignmentStatus.OFFERED, db_index=True
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    offered_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-offered_at"]
        constraints = [
            # A responder can hold only one live offer/assignment per incident,
            # and (with the service-level lock) only one live one overall.
            models.UniqueConstraint(
                fields=["incident", "responder"],
                condition=Q(status__in=["OFFERED", "ACCEPTED"]),
                name="one_active_assignment_per_incident_responder",
            ),
        ]
