from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accounts.models import Role
from apps.accounts.permissions import admin_required, ops_required
from apps.analytics import services as analytics
from apps.audit.models import AuditLog
from apps.audit.services import log as audit_log
from apps.dispatch.models import ACTIVE_ASSIGNMENT_STATUSES, DispatcherProfile
from apps.dispatch.selectors import available_responders_near
from apps.dispatch.services import AssignmentError, assign_responder, cancel_offer
from apps.incidents.models import ACTIVE_STATUSES, Category, Incident, Source, Status
from apps.incidents.services import InvalidTransition, change_status, create_incident, manual_transitions
from apps.notifications.models import Notification
from apps.responders.models import Availability, ResponderProfile
from apps.stations.models import Station
from apps.vehicles.models import Vehicle

from .forms import (
    DispatcherCreateForm,
    IncidentLogForm,
    ResponderCreateForm,
    StationForm,
    StatusUpdateForm,
    VehicleForm,
)

User = get_user_model()


def _paginate(request, qs, per_page=20):
    page = Paginator(qs, per_page).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return page, params.urlencode()


def _incident_marker(i):
    return {
        "id": i.pk,
        "category": i.get_category_display(),
        "status": i.status,
        "status_label": i.get_status_display(),
        "address": i.address_text,
        "lat": i.lat,
        "lng": i.lng,
        "url": f"/dashboard/incidents/{i.pk}/",
    }


def _responder_marker(r):
    return {
        "id": r.pk,
        "name": r.user.display_name,
        "availability": r.get_availability_display(),
        "lat": r.lat,
        "lng": r.lng,
        "stale": r.location_is_stale,
        "updated": r.last_location_at.isoformat() if r.last_location_at else None,
    }


# ---------- overview ----------
@ops_required
def overview(request):
    active = Incident.objects.filter(status__in=ACTIVE_STATUSES).select_related("citizen")
    markers = [_incident_marker(i) for i in active if i.has_location]
    responders = ResponderProfile.objects.filter(
        user__is_active=True, last_latitude__isnull=False, last_longitude__isnull=False
    ).select_related("user")
    return render(
        request,
        "dashboard/overview.html",
        {
            "stats": analytics.dashboard_stats(),
            "recent": active.order_by("-created_at")[:10],
            "incident_markers": markers,
            "responder_markers": [_responder_marker(r) for r in responders],
        },
    )


@ops_required
def stats_api(request):
    return JsonResponse(analytics.dashboard_stats())


@ops_required
def new_incidents_api(request):
    """Incidents created after the given id; polled by the alert banner."""
    try:
        after = int(request.GET.get("after", "0"))
    except ValueError:
        after = 0
    rows = list(Incident.objects.select_related("citizen").filter(pk__gt=after).order_by("pk")[:20])
    items = [
        {
            "id": i.pk,
            "category": i.get_category_display(),
            "where": i.address_text or ("GPS location" if i.has_location else ""),
            "reporter": i.reporter_display,
            "url": reverse("dashboard:incident_detail", args=[i.pk]),
        }
        for i in rows
    ]
    return JsonResponse({"latest_id": items[-1]["id"] if items else after, "new": items})


# ---------- incidents ----------
@ops_required
def incident_list(request):
    qs = Incident.objects.select_related("citizen")
    status = request.GET.get("status", "")
    category = request.GET.get("category", "")
    q = request.GET.get("q", "").strip()
    if status in Status.values:
        qs = qs.filter(status=status)
    if category in Category.values:
        qs = qs.filter(category=category)
    if q:
        cond = (
            Q(description__icontains=q)
            | Q(address_text__icontains=q)
            | Q(reporter_name__icontains=q)
            | Q(citizen__email__icontains=q)
            | Q(citizen__first_name__icontains=q)
            | Q(citizen__last_name__icontains=q)
        )
        if q.isdigit():
            cond |= Q(pk=int(q))
        qs = qs.filter(cond)
    page, qstring = _paginate(request, qs)
    return render(
        request,
        "dashboard/incident_list.html",
        {
            "page": page,
            "qstring": qstring,
            "status": status,
            "category": category,
            "q": q,
            "statuses": Status.choices,
            "categories": Category.choices,
        },
    )


@ops_required
def incident_create(request):
    form = IncidentLogForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        lat, lng = d.get("latitude"), d.get("longitude")
        incident = create_incident(
            category=d["category"],
            description=d["description"],
            reporter_name=d["reporter_name"],
            reporter_phone=d["reporter_phone"],
            address_text=d["address_text"],
            lat=lat,
            lng=lng,
            location_source="MANUAL" if lat is not None else "",
            source=Source.DISPATCHER,
            created_by=request.user,
            request=request,
        )
        messages.success(request, f"Incident #{incident.pk} logged.")
        return redirect("dashboard:incident_detail", pk=incident.pk)
    return render(request, "dashboard/form.html", {"form": form, "title": "Log an incident", "submit": "Log incident"})


@ops_required
def incident_detail(request, pk):
    incident = get_object_or_404(Incident.objects.select_related("citizen"), pk=pk)
    allowed = manual_transitions(incident.status)
    markers = [_incident_marker(incident)] if incident.has_location else []
    return render(
        request,
        "dashboard/incident_detail.html",
        {
            "incident": incident,
            "history": incident.history.select_related("changed_by"),
            "assignments": incident.assignments.select_related("responder__user", "vehicle"),
            "candidates": available_responders_near(incident) if incident.status in ACTIVE_STATUSES else [],
            "status_form": StatusUpdateForm(allowed=allowed) if allowed else None,
            "media": incident.media.all(),
            "incident_markers": markers,
            "responder_markers": [],
        },
    )


@ops_required
@require_POST
def incident_assign(request, pk):
    try:
        assign_responder(pk, request.POST.get("responder_id"), request.user, request=request)
        messages.success(request, "Dispatch offer sent to the responder.")
    except (AssignmentError, ResponderProfile.DoesNotExist, Incident.DoesNotExist, ValueError) as exc:
        messages.error(request, str(exc) if isinstance(exc, AssignmentError) else "Could not create that assignment.")
    return redirect("dashboard:incident_detail", pk=pk)


@ops_required
@require_POST
def incident_status(request, pk):
    incident = get_object_or_404(Incident, pk=pk)
    form = StatusUpdateForm(request.POST, allowed=manual_transitions(incident.status))
    if form.is_valid():
        try:
            change_status(pk, form.cleaned_data["status"], user=request.user, note=form.cleaned_data["note"], request=request)
            messages.success(request, "Status updated.")
        except InvalidTransition as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "That status change is not allowed from the current status.")
    return redirect("dashboard:incident_detail", pk=pk)


@ops_required
@require_POST
def assignment_cancel(request, pk):
    from apps.dispatch.models import IncidentAssignment

    assignment = get_object_or_404(IncidentAssignment, pk=pk)
    try:
        cancel_offer(pk, request.user, request=request)
        messages.success(request, "Offer withdrawn.")
    except AssignmentError as exc:
        messages.error(request, str(exc))
    return redirect("dashboard:incident_detail", pk=assignment.incident_id)


# ---------- responders / dispatchers / citizens ----------
@ops_required
def responder_list(request):
    qs = ResponderProfile.objects.select_related("user", "station", "vehicle").order_by("user__first_name")
    availability = request.GET.get("availability", "")
    if availability in Availability.values:
        qs = qs.filter(availability=availability)
    page, qstring = _paginate(request, qs)
    return render(
        request,
        "dashboard/responder_list.html",
        {"page": page, "qstring": qstring, "availability": availability, "availabilities": Availability.choices},
    )


@admin_required
def responder_create(request):
    form = ResponderCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        profile = form.save()
        audit_log(request.user, "responder.create", profile, request=request)
        messages.success(request, f"Responder account created for {profile.user.email}.")
        return redirect("dashboard:responder_list")
    return render(request, "dashboard/form.html", {"form": form, "title": "Add responder", "submit": "Create responder"})


@admin_required
def dispatcher_list(request):
    qs = DispatcherProfile.objects.select_related("user", "station").order_by("user__first_name")
    page, qstring = _paginate(request, qs)
    return render(request, "dashboard/dispatcher_list.html", {"page": page, "qstring": qstring})


@admin_required
def dispatcher_create(request):
    form = DispatcherCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        profile = form.save()
        audit_log(request.user, "dispatcher.create", profile, request=request)
        messages.success(request, f"Dispatcher account created for {profile.user.email}.")
        return redirect("dashboard:dispatcher_list")
    return render(request, "dashboard/form.html", {"form": form, "title": "Add dispatcher", "submit": "Create dispatcher"})


@ops_required
def citizen_list(request):
    qs = User.objects.filter(role=Role.CITIZEN).annotate(incident_count=Count("incidents")).order_by("-date_joined")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(phone__icontains=q))
    page, qstring = _paginate(request, qs)
    return render(request, "dashboard/citizen_list.html", {"page": page, "qstring": qstring, "q": q})


@admin_required
@require_POST
def user_toggle_active(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.pk == request.user.pk:
        messages.error(request, "You cannot deactivate your own account.")
    elif user.role == Role.ADMIN:
        messages.error(request, "Administrator accounts are managed in Django admin.")
    else:
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        audit_log(request.user, "user.activate" if user.is_active else "user.deactivate", user, request=request)
        messages.success(request, f"{user.email} is now {'active' if user.is_active else 'deactivated'}.")
    return redirect(request.POST.get("next") or "dashboard:overview")


# ---------- stations / vehicles ----------
@ops_required
def station_list(request):
    stations = Station.objects.annotate(responder_count=Count("responders", distinct=True), vehicle_count=Count("vehicles", distinct=True))
    return render(request, "dashboard/station_list.html", {"stations": stations})


@admin_required
def station_create(request):
    form = StationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        station = form.save()
        audit_log(request.user, "station.create", station, request=request)
        messages.success(request, "Station added.")
        return redirect("dashboard:station_list")
    return render(request, "dashboard/form.html", {"form": form, "title": "Add station", "submit": "Save station"})


@ops_required
def vehicle_list(request):
    return render(request, "dashboard/vehicle_list.html", {"vehicles": Vehicle.objects.select_related("station")})


@admin_required
def vehicle_create(request):
    form = VehicleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        vehicle = form.save()
        audit_log(request.user, "vehicle.create", vehicle, request=request)
        messages.success(request, "Vehicle added.")
        return redirect("dashboard:vehicle_list")
    return render(request, "dashboard/form.html", {"form": form, "title": "Add vehicle", "submit": "Save vehicle"})


# ---------- notifications, analytics, audit ----------
@ops_required
def notification_list(request):
    qs = Notification.objects.filter(user=request.user).select_related("incident")
    page, qstring = _paginate(request, qs, per_page=30)
    return render(request, "dashboard/notification_list.html", {"page": page, "qstring": qstring})


@ops_required
@require_POST
def notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect("dashboard:notification_list")


@ops_required
def analytics_view(request):
    daily = analytics.daily_incident_counts(14)
    peak = max((n for _, n in daily), default=0) or 1
    return render(
        request,
        "dashboard/analytics.html",
        {
            "stats": analytics.dashboard_stats(),
            "by_status": analytics.incidents_by_status(),
            "by_category": analytics.incidents_by_category(),
            "daily": [(d, n, round(n * 100 / peak)) for d, n in daily],
            "avg_resolution": analytics.average_resolution_minutes(),
        },
    )


@admin_required
def audit_log_view(request):
    qs = AuditLog.objects.select_related("user")
    action = request.GET.get("action", "").strip()
    if action:
        qs = qs.filter(action__icontains=action)
    page, qstring = _paginate(request, qs, per_page=50)
    return render(request, "dashboard/audit_log.html", {"page": page, "qstring": qstring, "action": action})
