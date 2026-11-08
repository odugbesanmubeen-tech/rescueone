from django.db import transaction
from django.utils import timezone

from apps.audit.services import log as audit_log
from apps.notifications.services import notify, notify_ops

from .models import Incident, IncidentStatusHistory, LocationSource, Source, Status, TERMINAL_STATUSES


class InvalidTransition(Exception):
    pass


ALLOWED_TRANSITIONS = {
    Status.REPORTED: {Status.DISPATCH_PENDING, Status.CANCELLED, Status.FALSE_ALARM},
    Status.DISPATCH_PENDING: {Status.REPORTED, Status.ASSIGNED, Status.CANCELLED, Status.FALSE_ALARM},
    Status.ASSIGNED: {Status.EN_ROUTE, Status.CANCELLED, Status.FALSE_ALARM},
    Status.EN_ROUTE: {Status.ON_SCENE, Status.CANCELLED, Status.FALSE_ALARM},
    Status.ON_SCENE: {Status.RESOLVED, Status.FALSE_ALARM},
    Status.RESOLVED: set(),
    Status.CANCELLED: set(),
    Status.FALSE_ALARM: set(),
}

# Statuses a person may set by hand. REPORTED / DISPATCH_PENDING / ASSIGNED are
# driven by dispatch actions (offer, accept, decline) so they stay consistent
# with the assignment records.
MANUAL_STATUSES = {Status.EN_ROUTE, Status.ON_SCENE, Status.RESOLVED, Status.CANCELLED, Status.FALSE_ALARM}


def manual_transitions(current_status):
    return [s for s in Status if s in ALLOWED_TRANSITIONS.get(current_status, set()) and s in MANUAL_STATUSES]


@transaction.atomic
def create_incident(
    *,
    category,
    description="",
    citizen=None,
    reporter_name="",
    reporter_phone="",
    address_text="",
    lat=None,
    lng=None,
    location_source="",
    accuracy_m=None,
    source=Source.CITIZEN_APP,
    created_by=None,
    request=None,
):
    has_point = lat is not None and lng is not None
    captured_at = None
    if has_point:
        lat, lng = float(lat), float(lng)
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise ValueError("Latitude or longitude is out of range.")
        captured_at = timezone.now()
        location_source = location_source or LocationSource.GPS
    else:
        lat = lng = None
    if not has_point and not address_text.strip():
        raise ValueError("An incident needs a location or an address.")

    incident = Incident.objects.create(
        citizen=citizen,
        reporter_name=reporter_name,
        reporter_phone=reporter_phone,
        source=source,
        category=category,
        description=description,
        latitude=lat,
        longitude=lng,
        location_source=location_source if has_point else "",
        location_accuracy_m=accuracy_m,
        location_captured_at=captured_at,
        address_text=address_text.strip(),
    )
    IncidentStatusHistory.objects.create(
        incident=incident, from_status="", to_status=Status.REPORTED, changed_by=created_by, note="Incident reported"
    )
    audit_log(created_by or citizen, "incident.create", incident, {"source": source}, request)
    notify_ops(
        f"New {incident.get_category_display().lower()} incident #{incident.pk}",
        incident=incident,
        kind="INCIDENT_NEW",
        exclude_user=created_by,
    )
    return incident


@transaction.atomic
def change_status(incident_id, new_status, user=None, note="", request=None):
    incident = Incident.objects.select_for_update().get(pk=incident_id)
    old = incident.status
    if new_status not in ALLOWED_TRANSITIONS.get(old, set()):
        raise InvalidTransition(f"Cannot change status from {old} to {new_status}.")

    incident.status = new_status
    update_fields = ["status", "updated_at"]
    if new_status in TERMINAL_STATUSES:
        incident.closed_at = timezone.now()
        update_fields.append("closed_at")
    incident.save(update_fields=update_fields)

    IncidentStatusHistory.objects.create(
        incident=incident, from_status=old, to_status=new_status, changed_by=user, note=note[:255]
    )
    if new_status in TERMINAL_STATUSES:
        _close_assignments(incident, new_status)

    audit_log(user, "incident.status", incident, {"from": old, "to": new_status, "note": note}, request)
    if incident.citizen_id:
        notify(
            incident.citizen,
            f"Your emergency #{incident.pk} is now: {incident.get_status_display()}",
            incident=incident,
            kind="STATUS",
        )
    return incident


def _close_assignments(incident, new_status):
    """Release responders when an incident reaches a terminal status."""
    from apps.dispatch.models import AssignmentStatus
    from apps.responders.models import Availability, ResponderProfile

    now = timezone.now()
    live = incident.assignments.select_for_update().filter(
        status__in=[AssignmentStatus.OFFERED, AssignmentStatus.ACCEPTED]
    )
    freed = []
    for a in live:
        if a.status == AssignmentStatus.ACCEPTED and new_status != Status.CANCELLED:
            a.status = AssignmentStatus.COMPLETED
        else:
            a.status = AssignmentStatus.CANCELLED
        a.closed_at = now
        a.save(update_fields=["status", "closed_at"])
        freed.append(a.responder_id)
    if freed:
        ResponderProfile.objects.filter(pk__in=freed, availability=Availability.BUSY).update(
            availability=Availability.ONLINE
        )
