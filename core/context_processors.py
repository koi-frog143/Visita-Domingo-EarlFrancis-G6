"""One route classification for both sidebar selection and breadcrumbs."""


SECTIONS = {
    "dashboard": {"dashboard", "admin_dashboard", "guard_dashboard", "resident_dashboard", "visitor_dashboard"},
    "profile": {"profile", "edit_profile"},
    "visits": {"visit_list", "visit_create", "visit_detail", "visit_edit", "visit_cancel", "visit_delete", "visit_decide"},
    "ids": {"id_list", "id_upload", "id_review", "id_file"},
}


def navigation(request):
    match = request.resolver_match
    route = match.url_name if match else None
    section = next((name for name, routes in SECTIONS.items() if route in routes), None)
    user = getattr(request, "user", None)
    labels = {
        "dashboard": "Dashboard",
        "profile": "My profile",
        "visits": "Visit requests",
        "ids": "ID review" if getattr(user, "role", None) == "ADMIN" else "My ID submissions",
    }
    return {"active_nav": section, "page_label": labels.get(section, "My space")}
