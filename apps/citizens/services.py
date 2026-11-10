import math

from apps.dispatch.models import AssignmentStatus
from apps.incidents.models import Category, Source, Status
from apps.incidents.services import InvalidTransition, change_status, create_incident
from apps.incidents.uploads import attach_media

CANCELLABLE = (Status.REPORTED, Status.DISPATCH_PENDING)


class SubmitError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def parse_coords(data):
    raw_lat, raw_lng = str(data.get("latitude", "") or "").strip(), str(data.get("longitude", "") or "").strip()
    if not raw_lat and not raw_lng:
        return None, None
    try:
        lat, lng = float(raw_lat), float(raw_lng)
    except ValueError:
        raise SubmitError("The location sent was not valid.")
    if not (math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180):
        raise SubmitError("The location sent was out of range.")
    return lat, lng


def submit_citizen_incident(user, data, files, request=None):
    """Validate input and create a real incident. Returns (incident, media_errors)."""
    category = data.get("category") or Category.OTHER
    if category not in Category.values:
        raise SubmitError("Choose a valid emergency type.")
    lat, lng = parse_coords(data)
    accuracy = None
    if data.get("accuracy"):
        try:
            accuracy = float(data["accuracy"])
        except ValueError:
            accuracy = None
        if accuracy is not None and (accuracy < 0 or not math.isfinite(accuracy)):
            accuracy = None
    try:
        incident = create_incident(
            category=category,
            description=str(data.get("description", "") or "").strip()[:2000],
            citizen=user,
            reporter_phone=user.phone,
            address_text=str(data.get("address_text", "") or "").strip()[:255],
            lat=lat,
            lng=lng,
            location_source="GPS" if lat is not None else "",
            accuracy_m=accuracy if lat is not None else None,
            source=Source.CITIZEN_APP,
            request=request,
        )
    except ValueError:
        raise SubmitError("We need your location or an address so responders can find you.")
    _, media_errors = attach_media(incident, files, user)
    return incident, media_errors


def cancel_incident(incident, user, request=None):
    if incident.status not in CANCELLABLE:
        raise SubmitError("This request can no longer be cancelled because help is already on the way.", 409)
    try:
        return change_status(incident.pk, Status.CANCELLED, user=user, note="Cancelled by citizen", request=request)
    except InvalidTransition as exc:
        raise SubmitError(str(exc), 409)


def incident_status_payload(incident):
    accepted = (
        incident.assignments.filter(status=AssignmentStatus.ACCEPTED).select_related("responder__user", "vehicle").first()
    )
    responder = None
    if accepted:
        r = accepted.responder
        responder = {
            "name": r.user.display_name,
            "type": r.get_responder_type_display(),
            "vehicle": accepted.vehicle.number if accepted.vehicle else "",
            "lat": r.lat,
            "lng": r.lng,
            "updated": r.last_location_at.isoformat() if r.last_location_at else None,
            "stale": r.location_is_stale,
        }
    return {
        "id": incident.pk,
        "status": incident.status,
        "status_label": incident.get_status_display(),
        "is_active": incident.is_active,
        "can_cancel": incident.status in CANCELLABLE,
        "lat": incident.lat,
        "lng": incident.lng,
        "pending_offer": incident.assignments.filter(status=AssignmentStatus.OFFERED).exists(),
        "responder": responder,
    }
