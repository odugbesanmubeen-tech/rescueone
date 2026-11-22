from django.urls import reverse

from apps.citizens.models import CitizenProfile
from apps.citizens.services import incident_status_payload


def user_json(user):
    data = {
        "id": user.pk,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
        "role": user.role,
        "address": "",
        "emergency_contact_name": "",
        "emergency_contact_phone": "",
    }
    profile = CitizenProfile.objects.filter(user=user).first()
    if profile:
        data.update(
            address=profile.address,
            emergency_contact_name=profile.emergency_contact_name,
            emergency_contact_phone=profile.emergency_contact_phone,
        )
    return data


def incident_summary(incident):
    return {
        "id": incident.pk,
        "category": incident.category,
        "category_label": incident.get_category_display(),
        "status": incident.status,
        "status_label": incident.get_status_display(),
        "is_active": incident.is_active,
        "description": incident.description,
        "address": incident.address_text,
        "lat": incident.lat,
        "lng": incident.lng,
        "created_at": incident.created_at.isoformat(),
    }


def incident_detail(incident):
    data = incident_summary(incident)
    data.update(incident_status_payload(incident))
    data["history"] = [
        {"status": h.to_status, "label": h.get_to_status_display(), "at": h.created_at.isoformat()}
        for h in incident.history.all()
    ]
    data["media"] = [
        {"id": m.pk, "type": m.media_type, "url": reverse("api:media", args=[m.pk])} for m in incident.media.all()
    ]
    return data


def notification_json(n):
    return {
        "id": n.pk,
        "message": n.message,
        "kind": n.kind,
        "incident_id": n.incident_id,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat(),
    }


# ---------- responder ----------
from apps.dispatch.models import AssignmentStatus  # noqa: E402
from apps.locations.utils import haversine_km  # noqa: E402


def profile_json(p):
    return {
        "availability": p.availability,
        "availability_label": p.get_availability_display(),
        "responder_type": p.get_responder_type_display(),
        "station": p.station.name if p.station else "",
        "vehicle": p.vehicle.number if p.vehicle else "",
        "lat": p.lat,
        "lng": p.lng,
        "location_at": p.last_location_at.isoformat() if p.last_location_at else None,
        "location_stale": p.location_is_stale,
    }


def assignment_json(a, profile):
    inc = a.incident
    distance = None
    if inc.has_location and profile.has_location:
        distance = round(haversine_km(inc.latitude, inc.longitude, profile.last_latitude, profile.last_longitude), 2)
    # The caller's phone number is shared only after the responder accepts.
    phone = ""
    if a.status == AssignmentStatus.ACCEPTED:
        phone = inc.citizen.phone if inc.citizen_id else inc.reporter_phone
    return {
        "id": a.pk,
        "status": a.status,
        "status_label": a.get_status_display(),
        "offered_at": a.offered_at.isoformat(),
        "responded_at": a.responded_at.isoformat() if a.responded_at else None,
        "distance_km": distance,
        "incident": {
            "id": inc.pk,
            "category": inc.category,
            "category_label": inc.get_category_display(),
            "status": inc.status,
            "status_label": inc.get_status_display(),
            "description": inc.description,
            "address": inc.address_text,
            "lat": inc.lat,
            "lng": inc.lng,
            "created_at": inc.created_at.isoformat(),
            "reporter_name": inc.reporter_display,
            "reporter_phone": phone,
            "media": [
                {"id": m.pk, "type": m.media_type, "url": reverse("api:media", args=[m.pk])} for m in inc.media.all()
            ],
        },
    }
