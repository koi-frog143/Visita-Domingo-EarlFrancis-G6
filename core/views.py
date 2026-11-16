from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from accounts.decorators import role_required
from accounts.models import CustomUser


def home(request):
    return render(request, "home.html")


@login_required
def dashboard(request):
    route_by_role = {
        CustomUser.Role.ADMIN: "admin_dashboard",
        CustomUser.Role.GUARD: "guard_dashboard",
        CustomUser.Role.RESIDENT: "resident_dashboard",
        CustomUser.Role.VISITOR: "visitor_dashboard",
    }
    route = route_by_role.get(request.user.role)
    if not route:
        raise PermissionDenied("Your account has no assigned dashboard.")
    return redirect(route)


@role_required(CustomUser.Role.ADMIN)
def admin_dashboard(request):
    return render(request, "dashboards/admin.html", {
        "total_users": CustomUser.objects.count(),
        "visitor_users": CustomUser.objects.filter(role=CustomUser.Role.VISITOR).count(),
        "resident_users": CustomUser.objects.filter(role=CustomUser.Role.RESIDENT).count(),
        "guard_users": CustomUser.objects.filter(role=CustomUser.Role.GUARD).count(),
    })


@role_required(CustomUser.Role.GUARD)
def guard_dashboard(request):
    return render(request, "dashboards/guard.html")


@role_required(CustomUser.Role.RESIDENT)
def resident_dashboard(request):
    unit = getattr(getattr(request.user, "resident_profile", None), "unit_number", "Not assigned yet")
    return render(request, "dashboards/resident.html", {"unit": unit})


@role_required(CustomUser.Role.VISITOR)
def visitor_dashboard(request):
    return render(request, "dashboards/visitor.html")
