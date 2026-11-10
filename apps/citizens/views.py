from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from apps.accounts.models import Role
from apps.accounts.permissions import citizen_required
from apps.audit.services import log as audit_log
from apps.incidents.models import ACTIVE_STATUSES, Category, Incident, Status
from apps.incidents.services import InvalidTransition, change_status
from apps.notifications.models import Notification

from .forms import CitizenLoginForm, ProfileForm, RegisterForm
from .models import CitizenProfile
from .services import CANCELLABLE, SubmitError, incident_status_payload, submit_citizen_incident


# ---------- auth ----------
@method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=True), name="post")
class CitizenLoginView(LoginView):
    template_name = "citizen/login.html"
    authentication_form = CitizenLoginForm
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        return reverse("citizens:home")

    def form_valid(self, form):
        response = super().form_valid(form)
        audit_log(self.request.user, "login", request=self.request)
        return response


@ratelimit(key="ip", rate="10/h", method="POST", block=True)
def register(request):
    if request.user.is_authenticated:
        return redirect("citizens:home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        audit_log(user, "citizen.register", user, request=request)
        login(request, user)
        messages.success(request, "Welcome. Your account is ready.")
        return redirect("citizens:home")
    return render(request, "citizen/register.html", {"form": form})


# ---------- pages ----------
@citizen_required
def home(request):
    mine = Incident.objects.filter(citizen=request.user)
    return render(
        request,
        "citizen/home.html",
        {
            "active": mine.filter(status__in=ACTIVE_STATUSES).first(),
            "recent": mine[:3],
            "categories": Category.choices,
        },
    )


@citizen_required
def report(request):
    return render(request, "citizen/report.html", {"categories": Category.choices})


@citizen_required
def incident_list(request):
    page = Paginator(Incident.objects.filter(citizen=request.user), 15).get_page(request.GET.get("page"))
    return render(request, "citizen/incident_list.html", {"page": page})


def _own_incident(request, pk):
    return get_object_or_404(Incident, pk=pk, citizen=request.user)


@citizen_required
def incident_detail(request, pk):
    incident = _own_incident(request, pk)
    return render(
        request,
        "citizen/incident_detail.html",
        {
            "incident": incident,
            "payload": incident_status_payload(incident),
            "history": incident.history.all(),
            "media": incident.media.all(),
            "can_cancel": incident.status in CANCELLABLE,
        },
    )


@citizen_required
@require_POST
def incident_cancel(request, pk):
    incident = _own_incident(request, pk)
    if incident.status not in CANCELLABLE:
        messages.error(request, "This request can no longer be cancelled because help is already on the way.")
    else:
        try:
            change_status(incident.pk, Status.CANCELLED, user=request.user, note="Cancelled by citizen", request=request)
            messages.success(request, "Your request was cancelled.")
        except InvalidTransition as exc:
            messages.error(request, str(exc))
    return redirect("citizens:incident_detail", pk=pk)


@citizen_required
def notification_list(request):
    page = Paginator(Notification.objects.filter(user=request.user).select_related("incident"), 20).get_page(
        request.GET.get("page")
    )
    return render(request, "citizen/notification_list.html", {"page": page})


@citizen_required
@require_POST
def notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect("citizens:notification_list")


@citizen_required
def profile(request):
    cp, _ = CitizenProfile.objects.get_or_create(user=request.user)
    initial = {
        "first_name": request.user.first_name,
        "last_name": request.user.last_name,
        "phone": request.user.phone,
        "address": cp.address,
        "emergency_contact_name": cp.emergency_contact_name,
        "emergency_contact_phone": cp.emergency_contact_phone,
    }
    form = ProfileForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        form.save(request.user)
        audit_log(request.user, "citizen.profile_update", request.user, request=request)
        messages.success(request, "Profile saved.")
        return redirect("citizens:profile")
    return render(request, "citizen/profile.html", {"form": form})


# ---------- JSON API ----------
@require_GET
def incident_status_api(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "Please sign in again."}, status=401)
    if request.user.role != Role.CITIZEN:
        return JsonResponse({"ok": False, "error": "Not allowed."}, status=403)
    incident = get_object_or_404(Incident, pk=pk, citizen=request.user)
    return JsonResponse({"ok": True, **incident_status_payload(incident)})


@require_POST
@ratelimit(key="user_or_ip", rate="6/m", method="POST", block=False)
def sos_api(request):
    """Create a real incident. The success response is sent only after the database save."""
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "Please sign in again."}, status=401)
    if request.user.role != Role.CITIZEN:
        return JsonResponse({"ok": False, "error": "Only citizen accounts can send emergency requests."}, status=403)
    if getattr(request, "limited", False):
        return JsonResponse({"ok": False, "error": "Too many requests. Wait a minute and try again."}, status=429)
    try:
        incident, media_errors = submit_citizen_incident(request.user, request.POST, request.FILES.getlist("media"), request)
    except SubmitError as exc:
        return JsonResponse({"ok": False, "error": exc.message}, status=exc.status)
    return JsonResponse(
        {
            "ok": True,
            "id": incident.pk,
            "status": incident.status,
            "url": reverse("citizens:incident_detail", args=[incident.pk]),
            "media_errors": media_errors,
        },
        status=201,
    )


# ---------- PWA ----------
def offline(request):
    return render(request, "citizen/offline.html")


def manifest(request):
    return JsonResponse(
        {
            "name": "Emergency Help",
            "short_name": "Emergency",
            "start_url": reverse("citizens:home"),
            "scope": "/app/",
            "display": "standalone",
            "orientation": "portrait",
            "background_color": "#ffffff",
            "theme_color": "#d62828",
            "icons": [
                {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
                {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
            ],
        },
        content_type="application/manifest+json",
    )


def service_worker(request):
    body = (Path(settings.BASE_DIR) / "static" / "pwa" / "sw.js").read_text(encoding="utf-8")
    response = HttpResponse(body, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/app/"
    response["Cache-Control"] = "no-cache"
    return response
