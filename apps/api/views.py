import mimetypes

from django.contrib.auth import authenticate
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit

from apps.accounts.models import AuthToken, Role
from apps.audit.services import log as audit_log
from apps.citizens.forms import ProfileForm, RegisterForm
from apps.citizens.models import CitizenProfile
from apps.citizens.services import SubmitError, cancel_incident, submit_citizen_incident
from apps.incidents.models import Incident, IncidentMedia
from apps.incidents.permissions import user_can_view_incident_files
from apps.notifications.models import Notification

from .auth import ApiError, api, read_json
from .serializers import incident_detail, incident_summary, notification_json, user_json

CITIZEN = (Role.CITIZEN,)
MOBILE_ROLES = (Role.CITIZEN, Role.RESPONDER)


def _form_errors(form):
    fields = {k: [e["message"] for e in v] for k, v in form.errors.get_json_data().items()}
    first = next(iter(fields.values()))[0] if fields else "Invalid input."
    return ApiError(first, 400, fields)


def _auth_response(request, user, device=""):
    raw = AuthToken.issue(user, name=device)
    audit_log(user, "login.api", request=request)
    return JsonResponse({"ok": True, "token": raw, "user": user_json(user)})


# ---------- auth ----------
@api(["POST"], auth=False)
@ratelimit(key="ip", rate="10/h", method="POST", block=False)
def register(request):
    if getattr(request, "limited", False):
        raise ApiError("Too many sign-ups from this network. Try again later.", 429)
    data = read_json(request)
    form = RegisterForm(
        {
            "first_name": data.get("first_name", ""),
            "last_name": data.get("last_name", ""),
            "email": data.get("email", ""),
            "phone": data.get("phone", ""),
            "password1": data.get("password", ""),
            "password2": data.get("password", ""),
        }
    )
    if not form.is_valid():
        raise _form_errors(form)
    user = form.save()
    audit_log(user, "citizen.register", user, request=request)
    return _auth_response(request, user, str(data.get("device", "")))


@api(["POST"], auth=False)
@ratelimit(key="ip", rate="10/m", method="POST", block=False)
def login(request):
    if getattr(request, "limited", False):
        raise ApiError("Too many attempts. Wait a minute and try again.", 429)
    data = read_json(request)
    email = str(data.get("email", "")).strip().lower()
    user = authenticate(request, username=email, password=str(data.get("password", "")))
    if user is None:
        raise ApiError("Incorrect email or password.", 400)
    if user.role not in MOBILE_ROLES:
        raise ApiError("This account is for the web dashboard. Sign in there instead.", 403)
    return _auth_response(request, user, str(data.get("device", "")))


@api(["POST"], roles=MOBILE_ROLES)
def logout(request):
    request.auth_token.delete()
    return JsonResponse({"ok": True})


@api(["GET", "PUT"], roles=CITIZEN)
def me(request):
    if request.method == "PUT":
        data = read_json(request)
        current = user_json(request.user)
        merged = {k: data.get(k, current[k]) for k in
                  ("first_name", "last_name", "phone", "address", "emergency_contact_name", "emergency_contact_phone")}
        form = ProfileForm(merged)
        if not form.is_valid():
            raise _form_errors(form)
        form.save(request.user)
        audit_log(request.user, "citizen.profile_update", request.user, request=request)
        request.user.refresh_from_db()
    return JsonResponse({"ok": True, "user": user_json(request.user)})


# ---------- incidents ----------
@api(["GET", "POST"], roles=CITIZEN)
@ratelimit(key="user", rate="6/m", method="POST", block=False)
def incidents(request):
    if request.method == "GET":
        rows = Incident.objects.filter(citizen=request.user)[:50]
        return JsonResponse({"ok": True, "results": [incident_summary(i) for i in rows]})
    if getattr(request, "limited", False):
        raise ApiError("Too many requests. Wait a minute and try again.", 429)
    try:
        incident, media_errors = submit_citizen_incident(request.user, request.POST, request.FILES.getlist("media"), request)
    except SubmitError as exc:
        raise ApiError(exc.message, exc.status)
    return JsonResponse({"ok": True, "incident": incident_detail(incident), "media_errors": media_errors}, status=201)


def _own(request, pk):
    return get_object_or_404(Incident, pk=pk, citizen=request.user)


@api(["GET"], roles=CITIZEN)
def incident_view(request, pk):
    return JsonResponse({"ok": True, "incident": incident_detail(_own(request, pk))})


@api(["POST"], roles=CITIZEN)
def incident_cancel(request, pk):
    incident = _own(request, pk)
    try:
        cancel_incident(incident, request.user, request)
    except SubmitError as exc:
        raise ApiError(exc.message, exc.status)
    incident.refresh_from_db()
    return JsonResponse({"ok": True, "incident": incident_detail(incident)})


@api(["GET"], roles=MOBILE_ROLES)
def media(request, pk):
    item = get_object_or_404(IncidentMedia.objects.select_related("incident"), pk=pk)
    if not user_can_view_incident_files(request.user, item.incident):
        raise ApiError("Not found.", 404)
    content_type = mimetypes.guess_type(item.file.name)[0] or "application/octet-stream"
    return FileResponse(item.file.open("rb"), content_type=content_type)


# ---------- notifications ----------
@api(["GET"], roles=CITIZEN)
def notifications(request):
    rows = Notification.objects.filter(user=request.user)[:50]
    unread = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({"ok": True, "unread": unread, "results": [notification_json(n) for n in rows]})


@api(["POST"], roles=CITIZEN)
def notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"ok": True})
