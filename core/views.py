from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from accounts.decorators import role_required
from accounts.models import CustomUser
from visits.models import IDDocument, VisitRequest


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
        "pending_ids": IDDocument.objects.filter(review_status="PENDING").count(),
        "total_visits": VisitRequest.objects.count(),
    })


@role_required(CustomUser.Role.GUARD)
def guard_dashboard(request):
    return render(request, "dashboards/guard.html")


@role_required(CustomUser.Role.RESIDENT)
def resident_dashboard(request):
    unit = getattr(getattr(request.user, "resident_profile", None), "unit_number", "Not assigned yet")
    return render(request, "dashboards/resident.html", {
        "unit": unit,
        "pending_visits": VisitRequest.objects.filter(resident__user=request.user, status="PENDING").count(),
    })


@role_required(CustomUser.Role.VISITOR)
def visitor_dashboard(request):
    return render(request, "dashboards/visitor.html", {
        "pending_visits": VisitRequest.objects.filter(visitor__user=request.user, status="PENDING").count(),
        "approved_visits": VisitRequest.objects.filter(visitor__user=request.user, status="APPROVED").count(),
        "verified_id": IDDocument.objects.filter(visitor__user=request.user, review_status="VERIFIED").exists(),
    })
