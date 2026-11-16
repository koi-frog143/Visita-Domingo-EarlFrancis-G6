"""Keep Django-managed data accessible through Django, including on Supabase."""
from django.db import migrations


def restrict_data_api(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    quote = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")
        roles = [quote(row[0]) for row in cursor.fetchall()]
        # PUBLIC is PostgreSQL's implicit all-users group.
        grantees = ", ".join(["PUBLIC", *roles])
        for model in apps.get_models(include_auto_created=True):
            if model._meta.app_label in {"accounts", "admin", "auth", "contenttypes", "sessions"}:
                cursor.execute(f"REVOKE ALL PRIVILEGES ON TABLE {quote(model._meta.db_table)} FROM {grantees}")


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("accounts", "0001_initial"),
        ("admin", "0003_logentry_add_action_flag_choices"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("sessions", "0001_initial"),
    ]
    # Rolling back application changes must not restore anonymous access.
    operations = [migrations.RunPython(restrict_data_api, migrations.RunPython.noop)]
