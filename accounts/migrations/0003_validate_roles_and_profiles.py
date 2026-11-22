from django.db import migrations, models


def check_existing_accounts(apps, schema_editor):
    using = schema_editor.connection.alias
    User = apps.get_model("accounts", "CustomUser")
    Resident = apps.get_model("accounts", "ResidentProfile")
    Visitor = apps.get_model("accounts", "VisitorProfile")
    invalid = User.objects.using(using).exclude(role__in=["ADMIN", "GUARD", "RESIDENT", "VISITOR"]).count()
    residents = Resident.objects.using(using).exclude(user__role="RESIDENT").count()
    visitors = Visitor.objects.using(using).exclude(user__role="VISITOR").count()
    if invalid or residents or visitors:
        raise RuntimeError(
            "Existing Visita records need review before role enforcement: "
            f"{invalid} invalid roles, {residents} incompatible Resident profiles, "
            f"{visitors} incompatible Visitor profiles. "
            "No accounts or passwords were changed. Back up the database and correct the records explicitly."
        )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_alter_customuser_phone")]
    operations = [
        migrations.RunPython(check_existing_accounts, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="customuser",
            constraint=models.CheckConstraint(
                condition=models.Q(role__in=["ADMIN", "GUARD", "RESIDENT", "VISITOR"]),
                name="valid_visita_user_role",
            ),
        ),
    ]
