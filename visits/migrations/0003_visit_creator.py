from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def link_existing_creators(apps, schema_editor):
    VisitRequest = apps.get_model("visits", "VisitRequest")
    for visit in VisitRequest.objects.using(schema_editor.connection.alias).select_related("visitor").all().iterator():
        VisitRequest.objects.using(schema_editor.connection.alias).filter(pk=visit.pk).update(created_by_id=visit.visitor.user_id)


class Migration(migrations.Migration):
    dependencies = [("visits", "0002_restrict_data_api"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name="visitrequest", name="created_by", field=models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="created_visits", to=settings.AUTH_USER_MODEL)),
        migrations.RunPython(link_existing_creators, migrations.RunPython.noop),
        migrations.AlterField(model_name="visitrequest", name="created_by", field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, related_name="created_visits", to=settings.AUTH_USER_MODEL)),
    ]
