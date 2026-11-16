from django.db import connection
from django.test import TestCase


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
