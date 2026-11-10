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
