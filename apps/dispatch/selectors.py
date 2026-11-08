from apps.locations.utils import haversine_km
from apps.responders.models import Availability, ResponderProfile


def available_responders_near(incident, limit=10):
    """Online responders, nearest first when both sides have coordinates.

    Each result gets a `distance_km` attribute (None when unknown).
    """
    responders = list(
        ResponderProfile.objects.filter(availability=Availability.ONLINE, user__is_active=True).select_related(
            "user", "station", "vehicle"
        )
    )
    for r in responders:
        r.distance_km = None
        if incident.has_location and r.has_location:
            r.distance_km = haversine_km(incident.latitude, incident.longitude, r.last_latitude, r.last_longitude)
    responders.sort(
        key=lambda r: (r.distance_km is None, r.distance_km if r.distance_km is not None else 0, r.user.first_name)
    )
    return responders[:limit]
