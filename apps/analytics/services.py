from datetime import timedelta

from django.db.models import Avg, Count, F, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.accounts.models import CustomUser, Role
from apps.incidents.models import Category, Incident, Status
from apps.responders.models import Availability, ResponderProfile


def dashboard_stats():
    """Every number comes from the database; nothing is cached or hardcoded."""
    inc = Incident.objects.aggregate(
        total_incidents=Count("id"),
        active_incidents=Count(
            "id",
            filter=Q(status__in=[Status.REPORTED, Status.DISPATCH_PENDING, Status.ASSIGNED, Status.EN_ROUTE, Status.ON_SCENE]),
        ),
        pending_incidents=Count("id", filter=Q(status__in=[Status.REPORTED, Status.DISPATCH_PENDING])),
        assigned_incidents=Count("id", filter=Q(status__in=[Status.ASSIGNED, Status.EN_ROUTE, Status.ON_SCENE])),
        resolved_incidents=Count("id", filter=Q(status=Status.RESOLVED)),
    )
    resp = ResponderProfile.objects.filter(user__is_active=True).aggregate(
        total_responders=Count("id"),
        available_responders=Count("id", filter=Q(availability=Availability.ONLINE)),
        busy_responders=Count("id", filter=Q(availability=Availability.BUSY)),
    )
    inc["total_citizens"] = CustomUser.objects.filter(role=Role.CITIZEN, is_active=True).count()
    return {**inc, **resp}


def incidents_by_status():
    counts = dict(Incident.objects.values_list("status").annotate(n=Count("id")))
    return [(label, counts.get(value, 0)) for value, label in Status.choices]


def incidents_by_category():
    counts = dict(Incident.objects.values_list("category").annotate(n=Count("id")))
    return [(label, counts.get(value, 0)) for value, label in Category.choices]


def daily_incident_counts(days=14):
    start = timezone.localdate() - timedelta(days=days - 1)
    rows = (
        Incident.objects.filter(created_at__date__gte=start)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(n=Count("id"))
    )
    by_day = {r["day"]: r["n"] for r in rows}
    return [(start + timedelta(days=i), by_day.get(start + timedelta(days=i), 0)) for i in range(days)]


def average_resolution_minutes():
    avg = Incident.objects.filter(status=Status.RESOLVED, closed_at__isnull=False).aggregate(
        avg=Avg(F("closed_at") - F("created_at"))
    )["avg"]
    return round(avg.total_seconds() / 60, 1) if avg else None
