from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.db import IntegrityError, transaction
from django.test import Client
from unittest.mock import patch
from .models import ResidentProfile, VisitorProfile

User = get_user_model()


class AccountsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.visitor = User.objects.create_user(email="visitor@example.com", full_name="Test Visitor", password="StrongPass123!", role="VISITOR")
        VisitorProfile.objects.create(user=cls.visitor)
        cls.resident = User.objects.create_user(email="resident@example.com", full_name="Test Resident", password="StrongPass123!", role="RESIDENT")
        ResidentProfile.objects.create(user=cls.resident, unit_number="101")
        cls.guard = User.objects.create_user(email="guard@example.com", full_name="Test Guard", password="StrongPass123!", role="GUARD")

    def test_registration_creates_visitor_and_profile(self):
        response = self.client.post(reverse("register"), {
            "full_name": "New Visitor", "email": "NEW@Example.com", "phone": "09123456789",
            "password1": "StrongPass123!", "password2": "StrongPass123!", "role": "ADMIN",
        })
        self.assertRedirects(response, reverse("login"))
        created = User.objects.get(email="new@example.com")
        self.assertEqual(created.role, "VISITOR")
        self.assertTrue(hasattr(created, "visitor_profile"))
        self.assertNotEqual(created.password, "StrongPass123!")
        self.assertTrue(created.check_password("StrongPass123!"))

    def test_duplicate_email_is_rejected_case_insensitively(self):
        response = self.client.post(reverse("register"), {
            "full_name": "Someone", "email": "VISITOR@EXAMPLE.COM", "phone": "",
            "password1": "StrongPass123!", "password2": "StrongPass123!",
        })
        self.assertContains(response, "already registered")
        self.assertEqual(User.objects.filter(email__iexact="visitor@example.com").count(), 1)

    def test_password_confirmation_is_validated(self):
        response = self.client.post(reverse("register"), {
            "full_name": "Someone", "email": "different@example.com", "phone": "",
            "password1": "StrongPass123!", "password2": "DifferentPass123!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="different@example.com").exists())

    def test_valid_login_and_logout(self):
        response = self.client.post(reverse("login"), {"username": "visitor@example.com", "password": "StrongPass123!"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))
        self.assertEqual(self.client.get(reverse("visitor_dashboard")).status_code, 200)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("login"))
        self.assertEqual(self.client.get(reverse("visitor_dashboard")).status_code, 302)

    def test_invalid_login(self):
        response = self.client.post(reverse("login"), {"username": "visitor@example.com", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_role_restriction(self):
        self.client.force_login(self.visitor)
        self.assertEqual(self.client.get(reverse("visitor_dashboard")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin_dashboard")).status_code, 403)
        self.assertEqual(self.client.get(reverse("guard_dashboard")).status_code, 403)
        self.assertEqual(self.client.get(reverse("resident_dashboard")).status_code, 403)

    def test_logged_out_redirects_to_login(self):
        response = self.client.get(reverse("admin_dashboard"))
        self.assertRedirects(response, reverse("login") + "?next=" + reverse("admin_dashboard"))

    def test_profile_changes_only_logged_in_user(self):
        self.client.force_login(self.visitor)
        response = self.client.post(reverse("edit_profile"), {
            "full_name": "Changed Visitor", "email": "updated@example.com", "phone": "09999999999", "role": "ADMIN",
        })
        self.assertRedirects(response, reverse("profile"))
        self.visitor.refresh_from_db()
        self.resident.refresh_from_db()
        self.assertEqual(self.visitor.full_name, "Changed Visitor")
        self.assertEqual(self.visitor.role, "VISITOR")
        self.assertEqual(self.resident.full_name, "Test Resident")

    def test_each_role_sees_only_own_dashboard(self):
        for user, allowed in [
            (self.visitor, "visitor_dashboard"),
            (self.resident, "resident_dashboard"),
            (self.guard, "guard_dashboard"),
        ]:
            self.client.force_login(user)
            response = self.client.get(reverse("dashboard"))
            self.assertEqual(response.url, reverse(allowed))
            self.assertEqual(self.client.get(reverse(allowed)).status_code, 200)

    def test_inactive_account_cannot_login(self):
        self.visitor.is_active = False
        self.visitor.save()
        response = self.client.post(reverse("login"), {
            "username": "visitor@example.com", "password": "StrongPass123!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_superuser_admin_account_creation_page(self):
        admin = User.objects.create_superuser(
            email="admin@example.com", full_name="Account Administrator", password="AdminStrong123!",
        )
        self.assertEqual(admin.role, "ADMIN")
        self.client.force_login(admin)
        response = self.client.get(reverse("admin:accounts_customuser_add"))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_add_guard_account(self):
        admin = User.objects.create_superuser(
            email="admin2@example.com", full_name="Admin Two", password="AdminStrong123!",
        )
        self.client.force_login(admin)
        response = self.client.post(reverse("admin:accounts_customuser_add"), {
            "email": "newguard@example.com", "full_name": "New Guard", "phone": "",
            "role": "GUARD", "password1": "GuardStrong123!", "password2": "GuardStrong123!",
            "is_active": "on",
            "_save": "Save",
        })
        self.assertEqual(response.status_code, 302, response.context and response.context.get("adminform"))
        created = User.objects.get(email="newguard@example.com")
        self.assertEqual(created.role, "GUARD")
        self.assertTrue(created.check_password("GuardStrong123!"))

    def test_profile_rejects_another_users_email(self):
        self.client.force_login(self.visitor)
        response = self.client.post(reverse("edit_profile"), {
            "full_name": "Test Visitor", "email": "RESIDENT@EXAMPLE.COM", "phone": "",
        })
        self.assertContains(response, "already registered")
        self.visitor.refresh_from_db()
        self.assertEqual(self.visitor.email, "visitor@example.com")

    def test_profile_requires_login(self):
        for route in ("profile", "edit_profile"):
            with self.subTest(route=route):
                self.assertRedirects(self.client.get(reverse(route)),
                                     reverse("login") + "?next=" + reverse(route))

    def test_get_logout_does_not_end_session(self):
        self.client.force_login(self.visitor)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_uppercase_email_login(self):
        response = self.client.post(reverse("login"), {
            "username": "VISITOR@EXAMPLE.COM", "password": "StrongPass123!",
        })
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        self.assertIn("_auth_user_id", self.client.session)

    def test_admin_dashboard_and_cross_role_denial(self):
        admin = User.objects.create_superuser(
            email="dashboard-admin@example.com", full_name="Dashboard Admin", password="AdminStrong123!",
        )
        users = [(admin, "admin_dashboard"), (self.visitor, "visitor_dashboard"),
                 (self.guard, "guard_dashboard"), (self.resident, "resident_dashboard")]
        routes = [route for _, route in users]
        for user, allowed in users:
            self.client.force_login(user)
            for route in routes:
                with self.subTest(role=user.role, route=route):
                    self.assertEqual(self.client.get(reverse(route)).status_code, 200 if route == allowed else 403)

    def test_registration_validates_required_fields_email_phone_and_password(self):
        valid = {"full_name": "New Visitor", "email": "new@example.com", "phone": "+63 912 345 6789",
                 "password1": "StrongPass123!", "password2": "StrongPass123!"}
        for changes in [{"full_name": " "}, {"email": ""}, {"email": "invalid"},
                        {"phone": "letters"}, {"phone": "-------"},
                        {"password1": "12345678", "password2": "12345678"}]:
            with self.subTest(changes=changes):
                response = self.client.post(reverse("register"), {**valid, **changes})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertFalse(User.objects.filter(email="new@example.com").exists())

    def test_registration_cannot_grant_staff_or_superuser_access(self):
        response = self.client.post(reverse("register"), {
            "full_name": "Unprivileged Visitor", "email": "unprivileged@example.com",
            "password1": "StrongPass123!", "password2": "StrongPass123!",
            "role": "ADMIN", "is_staff": "on", "is_superuser": "on",
        })
        self.assertRedirects(response, reverse("login"))
        user = User.objects.get(email="unprivileged@example.com")
        self.assertEqual(user.role, "VISITOR")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_registration_handles_simultaneous_duplicate_signup(self):
        with patch("accounts.forms.RegistrationForm.save", side_effect=IntegrityError("duplicate")):
            response = self.client.post(reverse("register"), {
                "full_name": "New Visitor", "email": "concurrent@example.com",
                "password1": "StrongPass123!", "password2": "StrongPass123!",
            })
        self.assertContains(response, "was just registered")
        self.assertFalse(User.objects.filter(email="concurrent@example.com").exists())

    def test_login_always_uses_the_role_dashboard(self):
        response = self.client.post(reverse("login") + "?next=" + reverse("admin_dashboard"), {
            "username": self.visitor.email, "password": "StrongPass123!",
        })
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("visitor_dashboard"))

    def test_profile_ignores_other_account_and_privilege_fields(self):
        self.client.force_login(self.visitor)
        response = self.client.post(reverse("edit_profile"), {
            "full_name": "Own Profile", "email": self.visitor.email, "phone": "+63 912 345 6789",
            "id": self.resident.pk, "user_id": self.resident.pk,
            "role": "ADMIN", "is_staff": "on", "is_superuser": "on", "password": "replaced",
        })
        self.assertRedirects(response, reverse("profile"))
        self.visitor.refresh_from_db()
        self.resident.refresh_from_db()
        self.assertEqual(self.visitor.full_name, "Own Profile")
        self.assertFalse(self.visitor.is_staff)
        self.assertFalse(self.visitor.is_superuser)
        self.assertTrue(self.visitor.check_password("StrongPass123!"))
        self.assertEqual(self.resident.full_name, "Test Resident")
        response = self.client.get(reverse("profile"), {"user_id": self.resident.pk})
        self.assertContains(response, self.visitor.email)
        self.assertNotContains(response, self.resident.email)

    def test_profile_concurrent_duplicate_email_is_a_form_error(self):
        self.client.force_login(self.visitor)
        with patch("accounts.forms.ProfileUpdateForm.save", side_effect=IntegrityError("duplicate")):
            response = self.client.post(reverse("edit_profile"), {
                "full_name": "Changed", "email": "claimed@example.com", "phone": "",
            })
        self.assertContains(response, "already registered")
        self.visitor.refresh_from_db()
        self.assertEqual(self.visitor.email, "visitor@example.com")

    def test_database_enforces_case_insensitive_email_uniqueness(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            # bypass save() normalization to test the database constraint itself
            User.objects.bulk_create([User(email="VISITOR@EXAMPLE.COM", full_name="Duplicate")])

    def test_account_post_forms_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("register"), {}).status_code, 403)
        self.assertEqual(client.post(reverse("login"), {}).status_code, 403)
        client.force_login(self.visitor)
        self.assertEqual(client.post(reverse("edit_profile"), {}).status_code, 403)
        self.assertEqual(client.post(reverse("logout"), {}).status_code, 403)

    def test_profile_escapes_user_supplied_html(self):
        self.visitor.full_name = "<script>alert('x')</script>"
        self.visitor.save()
        self.client.force_login(self.visitor)
        response = self.client.get(reverse("profile"))
        self.assertNotContains(response, "<script>alert('x')</script>")
        self.assertContains(response, "&lt;script&gt;")
