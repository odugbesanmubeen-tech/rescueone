from django.db import models


class ResponderLocation(models.Model):
    responder = models.ForeignKey("responders.ResponderProfile", on_delete=models.CASCADE, related_name="locations")
    latitude = models.FloatField()
    longitude = models.FloatField()
    accuracy_m = models.FloatField(null=True, blank=True)
    recorded_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [models.Index(fields=["responder", "-recorded_at"])]
