from .models import AuditLog


def log(user, action, target=None, details=None, request=None):
    ip = request.META.get("REMOTE_ADDR") if request is not None else None
    AuditLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        target_type=type(target).__name__ if target is not None else "",
        target_id=str(target.pk) if target is not None else "",
        details=details or {},
        ip_address=ip,
    )
