from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from html.parser import HTMLParser

from accounts.models import CustomUser, ResidentProfile, VisitorProfile
from visits.models import IDDocument, VisitRequest


class NavigationMarkup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.active_links = []
        self.current_links = []
        self.breadcrumb = []
        self.in_breadcrumb = False
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        classes = attrs.get("class", "").split()
        if tag == "p" and "breadcrumb" in classes:
            self.in_breadcrumb = True
        if tag == "a" and "nav-item" in classes:
            if "is-active" in classes:
                self.active_links.append(attrs["href"])
            if attrs.get("aria-current") == "page":
                self.current_links.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag == "p":
            self.in_breadcrumb = False

    def handle_data(self, value):
        if self.in_breadcrumb and value.strip():
            self.breadcrumb.append(value.strip())


class NavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = {
            role: CustomUser.objects.create_user(email=f"nav.{role.lower()}@example.com", full_name=f"Navigation {role}", role=role)
            for role in CustomUser.Role.values
        }
        visitor = VisitorProfile.objects.create(user=cls.users["VISITOR"])
        resident = ResidentProfile.objects.create(user=cls.users["RESIDENT"], unit_number="NAV-201")
        cls.visit = VisitRequest.objects.create(
            visitor=visitor, created_by=cls.users["VISITOR"], resident=resident,
            purpose="Navigation test", expected_start_at=timezone.now()+timedelta(days=2),
            expected_end_at=timezone.now()+timedelta(days=2, hours=1),
        )
        cls.document = IDDocument.objects.create(visitor=visitor, document_type="Sample ID", file="ids/navigation-test.png")

    def assert_navigation(self, route, section_url, label, args=None):
        response = self.client.get(reverse(route, args=args))
        self.assertEqual(response.status_code, 200)
        markup = NavigationMarkup(response.content.decode())
        self.assertEqual(markup.active_links, [reverse(section_url)])
        self.assertEqual(markup.current_links, [reverse(section_url)])
        self.assertEqual(markup.breadcrumb[-1], label)

    def test_all_role_dashboards_select_only_dashboard(self):
        for role, user in self.users.items():
            with self.subTest(role=role):
                self.client.force_login(user)
                self.assert_navigation(f"{role.lower()}_dashboard", "dashboard", "Dashboard")

    def test_profile_and_edit_select_only_profile_for_every_role(self):
        for role, user in self.users.items():
            self.client.force_login(user)
            for route in ["profile", "edit_profile"]:
                with self.subTest(role=role, route=route):
                    self.assert_navigation(route, "profile", "My profile")

    def test_visit_pages_keep_the_visit_section_selected(self):
        self.client.force_login(self.users["VISITOR"])
        for route in ["visit_list", "visit_create", "visit_detail", "visit_edit", "visit_cancel", "visit_delete"]:
            with self.subTest(route=route):
                args = None if route in ["visit_list", "visit_create"] else [self.visit.pk]
                self.assert_navigation(route, "visit_list", "Visit requests", args)
        for role in ["RESIDENT", "ADMIN"]:
            self.client.force_login(self.users[role])
            self.assert_navigation("visit_list", "visit_list", "Visit requests")
            self.assert_navigation("visit_detail", "visit_list", "Visit requests", [self.visit.pk])

    def test_id_pages_select_only_ids_and_use_the_role_label(self):
        self.client.force_login(self.users["VISITOR"])
        for route in ["id_list", "id_upload"]:
            self.assert_navigation(route, "id_list", "My ID submissions")
        self.client.force_login(self.users["ADMIN"])
        self.assert_navigation("id_list", "id_list", "ID review")
        self.assert_navigation("id_review", "id_list", "ID review", [self.document.pk])

    def test_guard_navigation_does_not_offer_restricted_workflows(self):
        self.client.force_login(self.users["GUARD"])
        response = self.client.get(reverse("guard_dashboard"))
        self.assertNotContains(response, f'href="{reverse("visit_list")}"')
        self.assertNotContains(response, f'href="{reverse("id_list")}"')
        self.assertEqual(self.client.get(reverse("visit_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("id_list")).status_code, 403)


class VisitDashboardTests(TestCase):
    def test_dashboard_actions_counts_and_ownership(self):
        visitor = CustomUser.objects.create_user(email="dash.visitor@example.com", full_name="Dashboard Visitor", role="VISITOR")
        other = CustomUser.objects.create_user(email="dash.other@example.com", full_name="Other Visitor", role="VISITOR")
        profile = VisitorProfile.objects.create(user=visitor)
        resident = CustomUser.objects.create_user(email="dash.resident@example.com", full_name="Dashboard Resident", role="RESIDENT")
        host = ResidentProfile.objects.create(user=resident, unit_number="201")
        VisitRequest.objects.create(visitor=profile, created_by=visitor, resident=host, purpose="Dashboard visit", expected_start_at=timezone.now()+timedelta(days=1), expected_end_at=timezone.now()+timedelta(days=1, hours=2))
        self.client.force_login(visitor)
        response = self.client.get(reverse("visitor_dashboard"))
        self.assertContains(response, "1 pending")
        self.assertContains(response, reverse("visit_list"))
        self.assertContains(response, reverse("id_list"))
        self.client.force_login(other)
        self.assertContains(self.client.get(reverse("visitor_dashboard")), "0 pending")
        self.client.force_login(resident)
        self.assertContains(self.client.get(reverse("resident_dashboard")), "1 pending request")


class DatabaseAccessTests(TestCase):
    def test_supabase_api_roles_cannot_access_django_data(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL permissions check")
        with connection.cursor() as cursor:
            cursor.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")
            roles = [row[0] for row in cursor.fetchall()]
            if not roles:
                self.skipTest("Supabase API roles are not installed on this PostgreSQL server")
            for role in roles:
                for table in ("accounts_customuser", "accounts_visitorprofile", "accounts_residentprofile", "django_session"):
                    for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                        with self.subTest(role=role, table=table, privilege=privilege):
                            cursor.execute("SELECT has_table_privilege(%s, %s, %s)", [role, table, privilege])
                            self.assertFalse(cursor.fetchone()[0])
