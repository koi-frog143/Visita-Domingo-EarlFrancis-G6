from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, ResidentProfile, VisitorProfile


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("email", "full_name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    ordering = ("email",)
    search_fields = ("email", "full_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal information", {"fields": ("full_name", "phone")}),
        ("Access", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined", "created_at")}),
    )
    readonly_fields = ("created_at", "last_login", "date_joined")
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "full_name", "phone", "role", "password1", "password2", "is_active", "is_staff")}),
    )


@admin.register(ResidentProfile)
class ResidentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "unit_number", "created_at")
    search_fields = ("user__email", "user__full_name", "unit_number")


@admin.register(VisitorProfile)
class VisitorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at")
    search_fields = ("user__email", "user__full_name")
