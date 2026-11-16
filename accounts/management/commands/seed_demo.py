"""Create clearly labelled lab accounts without changing existing accounts."""
import json
import secrets
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import CustomUser, ResidentProfile, VisitorProfile


class Command(BaseCommand):
    help = "Create four demo accounts; save generated passwords in .local/demo-accounts.json."

    def handle(self, *args, **options):
        path = Path(settings.BASE_DIR) / ".local" / "demo-accounts.json"
        path.parent.mkdir(exist_ok=True)
        credentials = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        created_count = 0
        with transaction.atomic():
            for role, name in (
                ("ADMIN", "Demo Administrator"),
                ("GUARD", "Demo Security Guard"),
                ("RESIDENT", "Demo Resident"),
                ("VISITOR", "Demo Visitor"),
            ):
                email = f"{role.lower()}@visita.example"
                if CustomUser.objects.filter(email=email).exists():
                    continue
                password = secrets.token_urlsafe(24)
                create = CustomUser.objects.create_superuser if role == "ADMIN" else CustomUser.objects.create_user
                user = create(email=email, full_name=name, password=password, role=role)
                if role == "RESIDENT":
                    ResidentProfile.objects.create(user=user, unit_number="101")
                elif role == "VISITOR":
                    VisitorProfile.objects.create(user=user)
                credentials[role] = {"email": email, "password": password}
                created_count += 1
        path.write_text(json.dumps(credentials, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Created {created_count} demo accounts. Private credentials: {path}"))
