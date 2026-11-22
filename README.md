# Visita - Phase 1

Digital visitor management for boarding houses and apartments using Django templates and PostgreSQL.

The frontend follows the [Haruhay Figma web design](https://www.figma.com/design/BrWLcw8zdtGPEEXgmSzRJ4/?node-id=73-2), adapted to Visita branding and Phase 1 account features. The cozy green palette uses forest `#285744`, sage `#E4EDDF`, cream `#FAF8F2`, and ink `#203D30`, inspired by the [separate Visita concept file](https://www.figma.com/design/d7KNK7ww1yisdPfF3hS9Fi). It preserves the local Figma illustrations/icons, DM Sans font, responsive layouts, split authentication pages, and sidebar dashboards. Font licensing is included in `static/fonts/OFL.txt`.

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

## Prepared copy and Git branch

The active repository is `~/Desktop/Visita/Visita-Domingo-EarlFrancis-G6`, on `feature/account-foundation`. The earlier standalone copy under Haruhay has been removed after consolidating its refinements here. Follow [GIT_WORKFLOW.md](GIT_WORKFLOW.md) for the two reviewed commit groups and push commands. No credentials or database files belong in a commit.

For this machine only, a private Python runtime and isolated PostgreSQL cluster are kept in ignored `.local/`. The private `.env` selects `visita_clone_dev` on localhost port `55439`, with `test_visita_clone_dev` used for tests. Start this prepared copy in Git Bash:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start-local-db.ps1
.local/python/python.exe manage.py migrate
.local/python/python.exe manage.py createsuperuser
.local/python/python.exe manage.py runserver 127.0.0.1:8001 --noreload
```

Choose your own Admin credentials at the prompt; no owner account is seeded. Stop Django with Ctrl+C, then run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/stop-local-db.ps1`. The scripts affect only `.local/postgres` in this repository. They do not start, migrate or reset any Supabase database. Fresh clones do not include these local tools; follow the standard setup below.

## Windows setup

Requires Python 3.12+ and Supabase or a local PostgreSQL database.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

For a fresh checkout, paste the generated key into `.env` in single quotes. Preserve an existing configured `.env`.

In Supabase, open **Connect > Direct > Session pooler**, then copy your exact host and username:

```dotenv
SECRET_KEY='YOUR_GENERATED_SECRET'
DEBUG=True
VISITA_DEBUG=True
DB_NAME=postgres
DB_USER=postgres.YOUR_PROJECT_REFERENCE
DB_PASSWORD='YOUR_PROJECT_DATABASE_PASSWORD'
DB_HOST=YOUR_SESSION_POOLER_HOST
DB_PORT=5432
DB_SSLMODE=require
DB_TEST_NAME=test_visita_phase1
```

API keys are not needed for this Django database connection. For local PostgreSQL, supply your local database credentials, `DB_HOST=127.0.0.1`, and `DB_SSLMODE=prefer`. `VISITA_DEBUG` takes precedence over `DEBUG` to avoid unrelated Windows environment variables disabling local static files.

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001
```

Open http://127.0.0.1:8001/. Port 8001 is used because port 8000 was unavailable on the lab machine.

## Accounts

Public registration at `/accounts/register/` creates a Visitor and VisitorProfile. Superusers have the Administrator role. Use `/admin/` to create Guard and Resident accounts and add a ResidentProfile with a unit number. Other accounts sign in at `/accounts/login/`.

Create labelled demonstration accounts with generated passwords:

```powershell
.\.venv\Scripts\python.exe manage.py seed_demo
```

Credentials are stored privately in `.local/demo-accounts.json`. Rerunning the command preserves existing accounts and passwords. Demo emails are `admin@visita.example`, `guard@visita.example`, `resident@visita.example`, and `visitor@visita.example`. The resident has unit `101`.

| Role | Dashboard |
| --- | --- |
| Administrator | `/dashboard/admin/` |
| Security Guard | `/dashboard/guard/` |
| Resident | `/dashboard/resident/` |
| Visitor | `/dashboard/visitor/` |

Profiles: `/accounts/profile/` and `/accounts/profile/edit/`.

## Verify

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

These commands check the project configuration and confirm model changes have migrations.

Tests use a separate database named by `DB_TEST_NAME`; choose a dedicated name, never the application database. The PostgreSQL role needs `CREATEDB`. Supabase's session pooler can retain a connection and prevent test database deletion, so use:

```powershell
.\.venv\Scripts\python.exe manage.py test --keepdb
```

The test database is retained between runs, and Django TestCase rolls back test data. The application's `postgres` database is separate.

For the prepared local-only copy, use `.local/python/python.exe manage.py test accounts core --noinput`; it creates and removes the dedicated test database. Use the same interpreter for `check` and `makemigrations --check --dry-run`. The Supabase-specific privilege test is skipped when Supabase API roles are absent on local PostgreSQL.

## Private files and database access

`.env`, `.venv/`, and `.local/` stay out of Git. Do not publish credentials, session data, or password hashes in screenshots. `DEBUG=True` is for local development.

The `core.0001_restrict_data_api` migration revokes PUBLIC and Supabase `anon`/`authenticated` table permissions on Django account, session, permission, and admin tables. Django uses its server-side database connection; Supabase Auth is not used. Review access if future migrations introduce tables.

Stack: Django 6.1.3, psycopg, python-dotenv, PostgreSQL, Django Templates, HTML/CSS. No SQLite runtime configuration is used.
