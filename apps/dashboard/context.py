from django.conf import settings

from apps.notifications.models import Notification


def dashboard_globals(request):
    ctx = {
        "MAP_CONFIG": {
            "lat": settings.MAP_DEFAULT_LAT,
            "lng": settings.MAP_DEFAULT_LNG,
            "zoom": settings.MAP_DEFAULT_ZOOM,
        }
    }
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        ctx["unread_notifications"] = Notification.objects.filter(user=user, is_read=False).count()
    return ctx
