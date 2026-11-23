from django.urls import path
from . import views

urlpatterns = [
    path("", views.visit_list, name="visit_list"),
    path("new/", views.visit_create, name="visit_create"),
    path("ids/", views.id_list, name="id_list"),
    path("ids/upload/", views.id_upload, name="id_upload"),
    path("ids/<uuid:pk>/review/", views.id_review, name="id_review"),
    path("ids/<uuid:pk>/file/", views.id_file, name="id_file"),
    path("<uuid:pk>/", views.visit_detail, name="visit_detail"),
    path("<uuid:pk>/edit/", views.visit_edit, name="visit_edit"),
    path("<uuid:pk>/cancel/", views.visit_cancel, name="visit_cancel"),
    path("<uuid:pk>/delete/", views.visit_delete, name="visit_delete"),
    path("<uuid:pk>/decide/", views.visit_decide, name="visit_decide"),
]
