from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Visita Administration"
admin.site.site_title = "Visita Admin"
admin.site.index_title = "Account Management"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("visits/", include("visits.urls")),
    path("", include("core.urls")),
]
