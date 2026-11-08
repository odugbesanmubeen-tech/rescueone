from django.contrib.auth import get_user_model

from apps.accounts.models import Role

from .models import Notification


def notify(user, message, incident=None, kind="SYSTEM"):
    return Notification.objects.create(user=user, message=message[:255], incident=incident, kind=kind)


def notify_ops(message, incident=None, kind="SYSTEM", exclude_user=None):
    """Create one stored notification per active dispatcher/admin."""
    User = get_user_model()
    users = User.objects.filter(is_active=True, role__in=[Role.DISPATCHER, Role.ADMIN])
    if exclude_user is not None:
        users = users.exclude(pk=exclude_user.pk)
    Notification.objects.bulk_create(
        [Notification(user=u, message=message[:255], incident=incident, kind=kind) for u in users]
    )
