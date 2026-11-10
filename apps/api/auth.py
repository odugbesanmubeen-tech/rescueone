import json
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.accounts.models import AuthToken


class ApiError(Exception):
    def __init__(self, message, status=400, fields=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.fields = fields or {}


def error_response(exc):
    body = {"ok": False, "error": exc.message}
    if exc.fields:
        body["fields"] = exc.fields
    return JsonResponse(body, status=exc.status)


def read_json(request):
    try:
        data = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        raise ApiError("Request body must be valid JSON.")
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object.")
    return data


def token_from_request(request):
    header = request.META.get("HTTP_AUTHORIZATION", "")
    parts = header.split()
    if len(parts) == 2 and parts[0].lower() == "token":
        return parts[1]
    return None


def authenticate_token(request):
    raw = token_from_request(request)
    if not raw:
        return None
    token = AuthToken.objects.select_related("user").filter(key_hash=AuthToken.hash_key(raw)).first()
    if token is None or not token.user.is_active:
        return None
    if timezone.now() - token.created_at > timedelta(days=settings.API_TOKEN_DAYS):
        return None
    now = timezone.now()
    if token.last_used_at is None or now - token.last_used_at > timedelta(minutes=1):
        AuthToken.objects.filter(pk=token.pk).update(last_used_at=now)
    request.auth_token = token
    return token.user


def api(methods, auth=True, roles=None):
    """JSON endpoint: method check, token auth, role check, uniform errors. CSRF does not apply to token auth."""

    def decorator(view):
        @csrf_exempt
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method not in methods:
                return JsonResponse({"ok": False, "error": "Method not allowed."}, status=405)
            try:
                if auth:
                    user = authenticate_token(request)
                    if user is None:
                        raise ApiError("Please sign in again.", 401)
                    if roles and user.role not in roles:
                        raise ApiError("This account cannot use this feature.", 403)
                    request.user = user
                return view(request, *args, **kwargs)
            except ApiError as exc:
                return error_response(exc)

        return wrapper

    return decorator
