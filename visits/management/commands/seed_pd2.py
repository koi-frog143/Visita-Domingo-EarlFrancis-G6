"""Create dedicated classroom accounts without altering existing credentials."""
import json
import secrets
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import CustomUser, ResidentProfile, VisitorProfile


class Command(BaseCommand):
    help = "Create dedicated PD2 test accounts; save their test passwords privately in .local/pd2-test-accounts.json."

    def handle(self, *args, **options):
        path = Path(settings.BASE_DIR) / ".local" / "pd2-test-accounts.json"
        path.parent.mkdir(exist_ok=True)
        credentials = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        count = 0
        with transaction.atomic():
            for role in CustomUser.Role.values:
                email = f"pd2.{role.lower()}@visita.example"
                existing = CustomUser.objects.filter(email=email).first()
                if existing:
                    if role not in credentials or not existing.check_password(credentials[role]["password"]):
                        raise CommandError(f"An existing {role} classroom account has no matching saved credentials; it was not changed.")
                    continue
                password = "PD2!" + secrets.token_urlsafe(12)
                # The classroom administrator uses the application review screens,
                # and does not get Django superuser/staff privileges.
                user = CustomUser.objects.create_user(email=email, full_name=f"PD2 Test {CustomUser.Role(role).label}", password=password, role=role)
                if role == CustomUser.Role.RESIDENT:
                    ResidentProfile.objects.create(user=user, unit_number="PD2-201")
                elif role == CustomUser.Role.VISITOR:
                    VisitorProfile.objects.create(user=user)
                credentials[role] = {"email": email, "password": password}
                count += 1
        path.write_text(json.dumps(credentials, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Created {count} classroom accounts. Test credentials saved to .local/pd2-test-accounts.json."))
