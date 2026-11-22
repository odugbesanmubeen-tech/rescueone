import math
import random
from datetime import timedelta

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_ratelimit.decorators import ratelimit

from apps.accounts.models import Role
from apps.audit.services import log as audit_log
from apps.dispatch.models import ACTIVE_ASSIGNMENT_STATUSES, AssignmentStatus, IncidentAssignment
from apps.dispatch.services import AssignmentError, respond_to_assignment
from apps.incidents.models import Status
from apps.incidents.services import InvalidTransition, change_status
from apps.locations.models import ResponderLocation
from apps.responders.models import Availability, ResponderProfile

from .auth import ApiError, api, read_json
from .serializers import assignment_json, profile_json

RESPONDER = (Role.RESPONDER,)


def _profile(user):
    try:
        return ResponderProfile.objects.select_related("station", "vehicle").get(user=user)
    except ResponderProfile.DoesNotExist:
        raise ApiError("Your responder profile is not set up. Ask an administrator.", 403)


def _queryset(profile):
    return (
        IncidentAssignment.objects.filter(responder=profile)
        .select_related("incident__citizen", "vehicle")
        .prefetch_related("incident__media")
    )


@api(["GET"], roles=RESPONDER)
def assignments(request):
    profile = _profile(request.user)
    qs = _queryset(profile)
    current = qs.filter(status__in=ACTIVE_ASSIGNMENT_STATUSES).order_by("offered_at")
    history = qs.exclude(status__in=ACTIVE_ASSIGNMENT_STATUSES).order_by("-offered_at")[:30]
    return JsonResponse(
        {
            "ok": True,
            "profile": profile_json(profile),
            "current": [assignment_json(a, profile) for a in current],
            "history": [assignment_json(a, profile) for a in history],
        }
    )


@api(["POST"], roles=RESPONDER)
def availability(request):
    user = request.user
    profile = _profile(user)
    target = read_json(request).get("availability")
    if target not in (Availability.ONLINE, Availability.OFFLINE):
        raise ApiError("Availability must be ONLINE or OFFLINE.")
    with transaction.atomic():
        locked = ResponderProfile.objects.select_for_update().get(pk=profile.pk)
        has_live = IncidentAssignment.objects.filter(responder=locked, status__in=ACTIVE_ASSIGNMENT_STATUSES).exists()
        if target == Availability.OFFLINE:
            if has_live:
                raise ApiError("Finish or decline your current assignment before going off duty.", 409)
            new = Availability.OFFLINE
        else:
            new = Availability.BUSY if (locked.availability == Availability.BUSY and has_live) else Availability.ONLINE
        if locked.availability != new:
            locked.availability = new
            locked.save(update_fields=["availability"])
            audit_log(user, "responder.availability", locked, {"to": new}, request)
    profile.refresh_from_db()
    return JsonResponse({"ok": True, "profile": profile_json(profile)})


@api(["POST"], roles=RESPONDER)
def respond(request, pk):
    profile = _profile(request.user)
    accept = read_json(request).get("accept")
    if not isinstance(accept, bool):
        raise ApiError("Send accept as true or false.")
    assignment = get_object_or_404(IncidentAssignment, pk=pk, responder=profile)
    try:
        respond_to_assignment(assignment.pk, request.user, accept, request)
    except AssignmentError as exc:
        raise ApiError(str(exc), 409)
    profile.refresh_from_db()
    assignment = get_object_or_404(_queryset(profile), pk=pk)
    return JsonResponse({"ok": True, "assignment": assignment_json(assignment, profile)})


@api(["POST"], roles=RESPONDER)
def update_status(request, pk):
    profile = _profile(request.user)
    target = read_json(request).get("status")
    if target not in (Status.EN_ROUTE, Status.ON_SCENE, Status.RESOLVED):
        raise ApiError("Status must be EN_ROUTE, ON_SCENE or RESOLVED.")
    assignment = get_object_or_404(_queryset(profile), pk=pk)
    if assignment.status != AssignmentStatus.ACCEPTED:
        raise ApiError("Accept this assignment before updating its status.", 409)
    incident = assignment.incident
    if incident.status != target:
        try:
            change_status(
                incident.pk, target, user=request.user, note=f"Updated by {request.user.display_name}", request=request
            )
        except InvalidTransition:
            raise ApiError(
                f"That update is not available while the incident is {incident.get_status_display().lower()}.", 409
            )
    profile.refresh_from_db()
    assignment = get_object_or_404(_queryset(profile), pk=pk)
    return JsonResponse({"ok": True, "assignment": assignment_json(assignment, profile)})


def _number(data, key, low, high, required=True):
    raw = data.get(key)
    if raw is None or raw == "":
        if required:
            raise ApiError(f"{key} is required.")
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ApiError(f"{key} must be a number.")
    if not math.isfinite(value) or not (low <= value <= high):
        raise ApiError(f"{key} is out of range.")
    return value


@api(["POST"], roles=RESPONDER)
@ratelimit(key="user", rate="30/m", method="POST", block=False)
def location(request):
    if getattr(request, "limited", False):
        raise ApiError("Too many location updates.", 429)
    profile = _profile(request.user)
    data = read_json(request)
    lat = _number(data, "latitude", -90, 90)
    lng = _number(data, "longitude", -180, 180)
    accuracy = _number(data, "accuracy", 0, 100000, required=False)
    if profile.availability == Availability.OFFLINE:
        raise ApiError("Go on duty to share your location.", 409)
    now = timezone.now()
    ResponderProfile.objects.filter(pk=profile.pk).update(
        last_latitude=lat, last_longitude=lng, last_location_accuracy_m=accuracy, last_location_at=now
    )
    ResponderLocation.objects.create(responder=profile, latitude=lat, longitude=lng, accuracy_m=accuracy, recorded_at=now)
    if random.random() < 0.02:  # keep the history table from growing forever
        ResponderLocation.objects.filter(responder=profile, recorded_at__lt=now - timedelta(days=7)).delete()
    return JsonResponse({"ok": True, "recorded_at": now.isoformat()})
