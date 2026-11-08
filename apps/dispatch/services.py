from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.services import log as audit_log
from apps.incidents.models import Incident, Status
from apps.incidents.services import change_status
from apps.notifications.services import notify, notify_ops
from apps.responders.models import Availability, ResponderProfile

from .models import ACTIVE_ASSIGNMENT_STATUSES, AssignmentStatus, IncidentAssignment


class AssignmentError(Exception):
    pass


DISPATCHABLE_STATUSES = [
    Status.REPORTED,
    Status.DISPATCH_PENDING,
    Status.ASSIGNED,
    Status.EN_ROUTE,
    Status.ON_SCENE,
]


@transaction.atomic
def assign_responder(incident_id, responder_id, user, request=None):
    """Offer an incident to a responder. Locks incident then responder (fixed order)."""
    incident = Incident.objects.select_for_update().get(pk=incident_id)
    responder = ResponderProfile.objects.select_for_update().select_related("user").get(pk=responder_id)

    if incident.status not in DISPATCHABLE_STATUSES:
        raise AssignmentError("This incident is closed and cannot be dispatched.")
    if not responder.user.is_active or responder.availability != Availability.ONLINE:
        raise AssignmentError("That responder is not available.")
    if IncidentAssignment.objects.filter(responder=responder, status__in=ACTIVE_ASSIGNMENT_STATUSES).exists():
        raise AssignmentError("That responder already has an active offer or assignment.")

    try:
        with transaction.atomic():
            assignment = IncidentAssignment.objects.create(
                incident=incident, responder=responder, vehicle=responder.vehicle, assigned_by=user
            )
    except IntegrityError:
        raise AssignmentError("That responder was already offered this incident.")

    if incident.status == Status.REPORTED:
        change_status(incident.pk, Status.DISPATCH_PENDING, user=user, note=f"Offered to {responder.user.display_name}")

    audit_log(user, "dispatch.offer", assignment, {"incident": incident.pk, "responder": responder.pk}, request)
    notify(
        responder.user,
        f"New dispatch offer for incident #{incident.pk} ({incident.get_category_display()})",
        incident=incident,
        kind="ASSIGNMENT_OFFER",
    )
    return assignment


def _revert_if_no_live_offers(incident, user, note):
    live = IncidentAssignment.objects.filter(incident=incident, status__in=ACTIVE_ASSIGNMENT_STATUSES).exists()
    incident.refresh_from_db()
    if not live and incident.status == Status.DISPATCH_PENDING:
        change_status(incident.pk, Status.REPORTED, user=user, note=note)


@transaction.atomic
def respond_to_assignment(assignment_id, user, accept, request=None):
    """Called by the responder who received the offer."""
    assignment = (
        IncidentAssignment.objects.select_for_update()
        .select_related("incident", "responder__user")
        .get(pk=assignment_id)
    )
    if assignment.responder.user_id != user.pk:
        raise AssignmentError("This assignment belongs to another responder.")
    if assignment.status != AssignmentStatus.OFFERED:
        raise AssignmentError("This offer is no longer open.")

    incident = Incident.objects.select_for_update().get(pk=assignment.incident_id)
    assignment.responded_at = timezone.now()

    if accept:
        if incident.status not in DISPATCHABLE_STATUSES:
            raise AssignmentError("This incident is already closed.")
        assignment.status = AssignmentStatus.ACCEPTED
        assignment.save(update_fields=["status", "responded_at"])
        ResponderProfile.objects.filter(pk=assignment.responder_id).update(availability=Availability.BUSY)
        if incident.status in (Status.REPORTED, Status.DISPATCH_PENDING):
            if incident.status == Status.REPORTED:
                change_status(incident.pk, Status.DISPATCH_PENDING, user=user, note="Offer pending")
            change_status(incident.pk, Status.ASSIGNED, user=user, note=f"Accepted by {user.display_name}")
        audit_log(user, "dispatch.accept", assignment, {"incident": incident.pk}, request)
        notify_ops(f"{user.display_name} accepted incident #{incident.pk}", incident=incident, kind="ASSIGNMENT_RESPONSE")
    else:
        assignment.status = AssignmentStatus.DECLINED
        assignment.closed_at = assignment.responded_at
        assignment.save(update_fields=["status", "responded_at", "closed_at"])
        _revert_if_no_live_offers(incident, user, f"Declined by {user.display_name}")
        audit_log(user, "dispatch.decline", assignment, {"incident": incident.pk}, request)
        notify_ops(f"{user.display_name} declined incident #{incident.pk}", incident=incident, kind="ASSIGNMENT_RESPONSE")
    return assignment


@transaction.atomic
def cancel_offer(assignment_id, user, request=None):
    assignment = (
        IncidentAssignment.objects.select_for_update()
        .select_related("incident", "responder__user")
        .get(pk=assignment_id)
    )
    if assignment.status != AssignmentStatus.OFFERED:
        raise AssignmentError("Only an open offer can be withdrawn.")
    assignment.status = AssignmentStatus.CANCELLED
    assignment.closed_at = timezone.now()
    assignment.save(update_fields=["status", "closed_at"])
    _revert_if_no_live_offers(assignment.incident, user, "Offer withdrawn")
    audit_log(user, "dispatch.cancel_offer", assignment, {"incident": assignment.incident_id}, request)
    notify(
        assignment.responder.user,
        f"Offer for incident #{assignment.incident_id} was withdrawn",
        incident=assignment.incident,
        kind="ASSIGNMENT_OFFER",
    )
    return assignment
