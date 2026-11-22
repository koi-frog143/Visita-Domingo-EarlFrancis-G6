# Visita - Phase 1

Digital visitor management for boarding houses and apartments using Django templates and PostgreSQL.

## Features

- Visitor registration with required full name, case-insensitive unique email validation, password confirmation, and optional validated contact number.
- Django password hashing, email login, CSRF protection, and POST-only logout.
- Administrator, Security Guard, Resident, and Visitor dashboards with server-side role checks.
- Profile viewing/editing restricted to the signed-in account. Public forms cannot change roles.
- Django Admin for creating guards/residents and assigning resident units.
- Supabase PostgreSQL with SSL and restricted API-role permissions on Django tables.
- Automated account, permission, profile, and database-access tests.
- Concurrent duplicate registration/profile emails return clear form errors, and login always opens the user's role dashboard.

QR passes, visit requests, ID review, scanning, and reporting belong to later phases.

## Technology and design

Full-stack Django serves HTML through Django templates. PostgreSQL, either local or hosted by Supabase, is the only configured database. Email is the unique login identifier. The UI uses forest green, sage and cream, with local SVG assets and DM Sans. Font licensing is in `static/fonts/OFL.txt`.

The revised [Software Design Document](docs/Domingo-EarlFrancis-SDD.pdf) reflects Django templates and PostgreSQL/Supabase. Its broader visitor/QR workflows describe later phases.

## Run this prepared Windows copy

Open Git Bash in `~/Desktop/Visita/Visita-Domingo-EarlFrancis-G6`. The private Python runtime in `.local/` is already installed. Your existing `.env` is preserved; keep its secret and database connection values private.

```bash
.local/python/python.exe manage.py check
.local/python/python.exe manage.py migrate
.local/python/python.exe manage.py runserver 127.0.0.1:8001 --noreload
```

Open http://127.0.0.1:8001/. Stop Django with Ctrl+C. Use your existing Admin login. On a new database only, create an Admin with `.local/python/python.exe manage.py createsuperuser`.

If `.env` selects the prepared local PostgreSQL instance on port 55439, start it with `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start-local-db.ps1`. Stop it afterward with `scripts/stop-local-db.ps1` using the same PowerShell flags. These scripts are unnecessary for Supabase.

## Fresh clone setup

Install Python 3.12+ and PostgreSQL, or use your Supabase development project. In Git Bash:

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
test -f .env || cp .env.example .env
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

On Linux/macOS activate with `source .venv/bin/activate`. Put the generated secret in `.env` for a new installation; preserve an existing configured secret.

In Supabase's Connect dialog select **Session pooler**, then copy its exact host and username into `.env`. Use your database password, not an API key:

```dotenv
SECRET_KEY='YOUR_GENERATED_SECRET'
DEBUG=True
VISITA_DEBUG=True
DB_NAME=postgres
DB_USER=postgres.YOUR_PROJECT_REFERENCE
DB_PASSWORD='YOUR_DATABASE_PASSWORD'
DB_HOST=YOUR_SESSION_POOLER_HOST
DB_PORT=5432
DB_SSLMODE=require
DB_TEST_NAME=test_visita_phase1
```

For local PostgreSQL, use a dedicated Visita database/user, `DB_HOST=127.0.0.1`, the correct port, and `DB_SSLMODE=prefer`. Never use the application database as `DB_TEST_NAME`. With your virtual environment active:

```bash
python manage.py check
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8001
```

## Applying the role/profile integrity update

Back up your target database before migrating. Migration `0003_validate_roles_and_profiles` checks existing records, then adds the four-value role constraint. It does not delete accounts, reset passwords, remove profiles, or rewrite roles. If incompatible records exist, it stops and reports counts; review those records explicitly before retrying. A valid existing Admin account keeps its password.

Existing Resident or Visitor profiles lock their account to the matching role. Django Admin displays an error for incompatible changes. Profiles cannot be reassigned between accounts. Deactivate accounts when access should end. Role changes without a linked profile remain possible, but superusers must remain staff Administrators. Profile writes and account saves lock the account row to serialize competing changes. Use model saves and validated forms for these operations; `QuerySet.update()`, `bulk_create()` and direct SQL bypass service validation and must not change profile ownership or otherwise-valid roles. Invalid role values are also rejected by the database.

## Pages and roles

| Page | URL |
| --- | --- |
| Register a Visitor | `/accounts/register/` |
| Log in | `/accounts/login/` |
| Profile / edit | `/accounts/profile/`, `/accounts/profile/edit/` |
| Role dashboard redirect | `/dashboard/` |
| Admin / Guard / Resident / Visitor | `/dashboard/admin/`, `/dashboard/guard/`, `/dashboard/resident/`, `/dashboard/visitor/` |
| Django administration | `/admin/` |

Log out with the navigation button (POST). Admins create Guard/Resident accounts and manage unit assignments. Public registration never grants privileged roles.

## Verify safely

Run tests against a dedicated local PostgreSQL development cluster with database-creation permission. After selecting that local connection in your private environment:

```bash
python manage.py test accounts core --noinput
python manage.py check
python manage.py makemigrations --check --dry-run
```

Replace `python` with `.local/python/python.exe` for the prepared runtime. The runner creates and removes a separate test database. The Supabase API-role test skips on local PostgreSQL without `anon`/`authenticated` roles. Do not run tests against a production connection or a shared database named as the test database.

## Secrets and commits

`.env`, `.local/`, virtual environments, generated credentials, uploads and Python caches are ignored. If a database password has been shared, rotate it in Supabase and update only the private `.env`; it is separate from your Django account password. Debug mode is for local development.

Follow [GIT_WORKFLOW.md](GIT_WORKFLOW.md) to push the integrity fix and documentation update on separate branches. No automatic commits or pushes are made.
