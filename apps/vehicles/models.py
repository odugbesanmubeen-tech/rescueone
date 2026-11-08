from django.db import models


class VehicleType(models.TextChoices):
    FIRE_TRUCK = "FIRE_TRUCK", "Fire truck"
    AMBULANCE = "AMBULANCE", "Ambulance"
    PATROL = "PATROL", "Patrol vehicle"
    RESCUE = "RESCUE", "Rescue vehicle"
    OTHER = "OTHER", "Other"


class Vehicle(models.Model):
    number = models.CharField("vehicle number", max_length=32, unique=True)
    vehicle_type = models.CharField(max_length=16, choices=VehicleType.choices, default=VehicleType.OTHER)
    station = models.ForeignKey(
        "stations.Station", null=True, blank=True, on_delete=models.SET_NULL, related_name="vehicles"
    )
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return f"{self.number} ({self.get_vehicle_type_display()})"
