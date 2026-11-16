from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/admin/", views.admin_dashboard, name="admin_dashboard"),
    path("dashboard/guard/", views.guard_dashboard, name="guard_dashboard"),
    path("dashboard/resident/", views.resident_dashboard, name="resident_dashboard"),
    path("dashboard/visitor/", views.visitor_dashboard, name="visitor_dashboard"),
]
