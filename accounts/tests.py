from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
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
