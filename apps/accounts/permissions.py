from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import Role


def role_required(*roles, login_url=None):
    """Login + role check, enforced on the server for every request."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return login_required(wrapper, login_url=login_url)

    return decorator


ops_required = role_required(Role.DISPATCHER, Role.ADMIN)
admin_required = role_required(Role.ADMIN)
citizen_required = role_required(Role.CITIZEN, login_url="/app/login/")
