from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.db import IntegrityError, transaction
from django.test import Client
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.contrib.auth.hashers import make_password
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


class RoleProfileIntegrityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.visitor = User.objects.create_user("integrity-visitor@example.com", full_name="Visitor")
        cls.visitor_profile = VisitorProfile.objects.create(user=cls.visitor)
        cls.resident = User.objects.create_user("integrity-resident@example.com", full_name="Resident", role="RESIDENT")
        cls.resident_profile = ResidentProfile.objects.create(user=cls.resident, unit_number="201")
        cls.admin = User.objects.create_superuser("integrity-admin@example.com", "AdminPass!847263", full_name="Admin")

    def test_invalid_role_rejected_by_model(self):
        with self.assertRaises(ValidationError):
            User.objects.create_user("invalid@example.com", full_name="Invalid", role="UNKNOWN")

    def test_invalid_role_rejected_by_database_even_when_save_is_bypassed(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=self.visitor.pk).update(role="UNKNOWN")

    def test_role_change_preserves_existing_profile_and_password(self):
        old_password = self.visitor.password
        self.visitor.role = "GUARD"
        with self.assertRaises(ValidationError):
            self.visitor.save()
        self.visitor.refresh_from_db()
        self.assertEqual(self.visitor.role, "VISITOR")
        self.assertEqual(self.visitor.password, old_password)
        self.assertTrue(VisitorProfile.objects.filter(user=self.visitor).exists())

    def test_admin_role_change_is_a_form_error(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("admin:accounts_customuser_change", args=[self.visitor.pk]), {
            "email": self.visitor.email, "full_name": self.visitor.full_name, "phone": "",
            "role": "GUARD", "is_active": "on", "_save": "Save",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This account has a Visitor profile")
        self.visitor.refresh_from_db()
        self.assertEqual(self.visitor.role, "VISITOR")

    def test_both_profile_types_and_wrong_role_are_rejected(self):
        with self.assertRaises(ValidationError):
            ResidentProfile.objects.create(user=self.visitor, unit_number="202")
        with self.assertRaises(ValidationError):
            VisitorProfile.objects.create(user=self.resident)

    def test_stale_cached_user_cannot_bypass_profile_role_validation(self):
        user = User.objects.create_user("stale@example.com", full_name="Stale", role="VISITOR")
        profile = VisitorProfile(user=user)
        User.objects.filter(pk=user.pk).update(role="GUARD")
        with self.assertRaises(ValidationError):
            profile.save()

    def test_existing_profiles_cannot_be_reassigned(self):
        other = User.objects.create_user("other@example.com", full_name="Other")
        self.visitor_profile.user = other
        with self.assertRaises(ValidationError):
            self.visitor_profile.save()
        self.visitor_profile.refresh_from_db()
        self.assertEqual(self.visitor_profile.user_id, self.visitor.pk)

    def test_normal_profile_edits_and_deactivation_still_work(self):
        self.resident_profile.unit_number = "303"
        self.resident_profile.save()
        self.resident.is_active = False
        self.resident.save()
        self.resident.refresh_from_db()
        self.assertFalse(self.resident.is_active)
        self.assertEqual(self.resident_profile.unit_number, "303")

    def test_superuser_cannot_be_demoted_to_another_role(self):
        self.admin.role = "GUARD"
        with self.assertRaises(ValidationError):
            self.admin.save()

    def test_role_changes_without_profiles_remain_allowed(self):
        user = User.objects.create_user("unlinked@example.com", full_name="Unlinked", role="GUARD")
        user.role = "RESIDENT"
        user.save()
        ResidentProfile.objects.create(user=user, unit_number="404")


class RoleIntegrityMigrationTests(TransactionTestCase):
    def test_migration_stops_for_legacy_conflicts_and_preserves_owner_credentials(self):
        before = [("accounts", "0002_alter_customuser_phone")]
        after = [("accounts", "0003_validate_roles_and_profiles")]
        executor = MigrationExecutor(connection)
        latest_targets = executor.loader.graph.leaf_nodes()
        executor.migrate(before)
        old_apps = executor.loader.project_state(before).apps
        LegacyUser = old_apps.get_model("accounts", "CustomUser")
        LegacyVisitor = old_apps.get_model("accounts", "VisitorProfile")
        owner = LegacyUser.objects.create(
            email="migration-owner@example.com", password=make_password("OwnerPassword!847263"),
            full_name="Owner", role="ADMIN", is_staff=True, is_superuser=True,
        )
        owner_hash = owner.password
        invalid = LegacyUser.objects.create(email="legacy@example.com", full_name="Legacy", role="UNKNOWN")
        try:
            with self.assertRaisesRegex(RuntimeError, "1 invalid roles"):
                MigrationExecutor(connection).migrate(after)
            self.assertEqual(LegacyUser.objects.get(pk=owner.pk).password, owner_hash)
            self.assertTrue(LegacyUser.objects.filter(pk=invalid.pk).exists())
            LegacyUser.objects.filter(pk=invalid.pk).update(role="GUARD")
            legacy_profile = LegacyVisitor.objects.create(user_id=invalid.pk)
            with self.assertRaisesRegex(RuntimeError, "1 incompatible Visitor profiles"):
                MigrationExecutor(connection).migrate(after)
            self.assertTrue(LegacyVisitor.objects.filter(pk=legacy_profile.pk).exists())
            legacy_profile.delete()
            MigrationExecutor(connection).migrate(after)
            current_owner = User.objects.get(pk=owner.pk)
            self.assertEqual(current_owner.password, owner_hash)
            self.assertTrue(current_owner.check_password("OwnerPassword!847263"))
            self.assertEqual(current_owner.role, "ADMIN")
        finally:
            LegacyVisitor.objects.filter(user_id=invalid.pk).delete()
            LegacyUser.objects.filter(pk=invalid.pk).update(role="GUARD")
            MigrationExecutor(connection).migrate(after)
            # Restore dependent apps too, including the PD2 visit tables.
            MigrationExecutor(connection).migrate(latest_targets)
