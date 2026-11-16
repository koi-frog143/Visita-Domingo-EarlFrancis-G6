from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(role):
    """Authentication plus server-side role enforcement (403 for wrong role)."""
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.user.role != role:
                raise PermissionDenied("You do not have access to this dashboard.")
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
