"""Keep private workflow records inaccessible to Supabase browser/API roles."""
from django.db import migrations


def restrict_data_api(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    quote = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")
        grantees = ", ".join(["PUBLIC", *[quote(row[0]) for row in cursor.fetchall()]])
        for name in ("AuditLog", "IDDocument", "VisitRequest"):
            model = apps.get_model("visits", name)
            cursor.execute(f"REVOKE ALL PRIVILEGES ON TABLE {quote(model._meta.db_table)} FROM {grantees}")


class Migration(migrations.Migration):
    dependencies = [("visits", "0001_initial"), ("core", "0001_restrict_data_api")]
    operations = [migrations.RunPython(restrict_data_api, migrations.RunPython.noop)]
