# Visita — Project Development 2

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

## PD2 core feature: visit requests and resident approval

The visitor-to-resident approval workflow now works end to end through Django templates and PostgreSQL/Supabase:

- Visitors choose an active resident/host, enter a purpose and future arrival/departure, and submit a persistent pending request.
- Every request has a protected `created_by` foreign key to the signed-in account, alongside its SDD visitor/resident profile relationships. The browser cannot choose another creator.
- Visitors view/filter their own requests, edit future pending requests, delete pending requests after confirmation, or cancel pending/approved requests while retaining history.
- Visitors submit a JPG/PNG ID image (maximum 5 MB). Administrators privately download and verify/reject submissions; rejection requires a reason.
- Only the addressed resident can approve/reject a future pending request. Approval requires an administrator-verified ID. Atomic locks prevent conflicting decisions from replacing an earlier result.
- Administrators view all requests without overriding resident decisions. Guards keep their existing account/dashboard access; pending requests and private IDs are restricted from this role.
- Protected profile/account relationships, database schedule/status/decision constraints and timestamped actor-linked audit entries preserve integrity. New tables revoke Supabase browser/API role access.
- Visitor, Resident and Administrator dashboards expose working links and database-derived counts. CSRF, validation errors, success messages and owner checks apply to writes.

This increment implements SDD F-04 plus its F-03 prerequisite. Temporary codes, QR passes, guard check-in/check-out, active-visitor monitoring and activity reports remain later work (F-05 to F-08). A resident approval is a planning record and does not grant a QR entry credential yet.

The linked [Figma account design](https://www.figma.com/design/d7KNK7ww1yisdPfF3hS9Fi/Visita---Visitor-Management?node-id=3-35) supplied DM Sans and the forest/sage/cream visual system. New request and ID views extend those patterns; the file does not contain exact PD2 screen layouts.

Follow the [manual Git workflow](GIT_WORKFLOW.md) to commit the dashboard integration and release through `develop`. The student completes the report and captures submission evidence manually; prepared report examples are kept local and excluded from this feature commit.

## Technology and design

Full-stack Django serves HTML through Django templates. PostgreSQL, either local or hosted by Supabase, is the only configured database. Email is the unique login identifier. The UI uses forest green, sage and cream, with local SVG assets and DM Sans. Font licensing is in `static/fonts/OFL.txt`.

The revised [Software Design Document](docs/Domingo-EarlFrancis-SDD.pdf) reflects Django templates and PostgreSQL/Supabase. Its broader QR/scanning/reporting workflows describe later phases. The older Downloads SDD's proposed React/Spring stack is superseded by the lab's Django requirement and this codebase.

## Run this prepared Windows copy

Open PowerShell in `C:\Users\L23X07W17\Visita-Domingo-EarlFrancis-G6`. The `.venv` runtime and existing `.env` are prepared; keep secret and database connection values private.

```powershell
.\.venv\Scripts\python.exe -B manage.py check
.\.venv\Scripts\python.exe -B manage.py migrate
.\.venv\Scripts\python.exe -B manage.py runserver 127.0.0.1:8001 --noreload
```

Open http://127.0.0.1:8001/. Stop Django with Ctrl+C. Use your existing Admin login. On a new database only, create an Admin with `python manage.py createsuperuser`. PD2 migrations are already applied to this prepared Supabase connection; `migrate` is safe to rerun.

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
| Visit list / new request | `/visits/`, `/visits/new/` |
| Visit details / edit / cancel / delete | `/visits/<uuid>/`, then `edit/`, `cancel/`, `delete/` |
| ID submissions / upload | `/visits/ids/`, `/visits/ids/upload/` |
| Administrator ID review / private download | `/visits/ids/<uuid>/review/`, `/visits/ids/<uuid>/file/` |

Log out with the navigation button (POST). Admins create Guard/Resident accounts and manage unit assignments. Public registration never grants privileged roles.

## Verify safely

Use a PostgreSQL development connection with database-creation permission. The helper creates a unique separate test database, refuses to reuse an existing database, runs checks, and removes only its own test database. On Supabase it handles retained session-pooler connections during teardown. It never chooses the application database as its test database.

```bash
python scripts/verify_pd2.py
python manage.py check
python manage.py makemigrations --check --dry-run
```

Replace `python` with `.\.venv\Scripts\python.exe` in the prepared PowerShell environment. The Supabase API-role test skips on a local server without `anon`/`authenticated` roles. The account migration regression restores every app's latest migrations after its temporary downgrade, including visit tables.

## Classroom accounts and browser checks

Create four separate test accounts without changing existing accounts/passwords:

```powershell
.\.venv\Scripts\python.exe -B manage.py seed_pd2
```

Credentials are generated into ignored `.local/pd2-test-accounts.json`. Open that private file to obtain the dedicated classroom credentials for your manual walkthrough. Its Administrator uses the application ID review UI, and has no Django staff/superuser privileges. The seed refuses to reset an existing account with missing/mismatched saved credentials.

To check desktop/mobile navigation and page rendering, install the optional development tools, keep Django running on port 8001, and run in another terminal:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -B scripts\verify_pd2.py
.\.venv\Scripts\python.exe -B scripts\check_ui.py
```

The browser check signs in as each classroom role, inspects dashboard/profile/request/ID pages, verifies one active navigation item and the matching breadcrumb, checks mobile overflow and image proportions, and exercises permission-denied pages. It reads existing business records without creating requests, uploading IDs or editing profiles. Local diagnostic previews/results are saved under ignored `.local/ui-regression/`; they are not submission evidence.

For a manual functional walkthrough, submit a future-dated request as Visitor, verify a sample ID as Administrator, approve/reject the addressed request as Resident, and confirm the stored result as Visitor. Use separate pending requests to demonstrate editing/deleting and cancellation. Test required fields, reversed arrival/departure times, rejected IDs without a reason and wrong-role URLs. QR scanning remains a later increment. Navigation uses exact route groups for all pages, so Visitor dashboards cannot also select Visit requests. Expired requests and stale action links show their current availability; repeated review submissions display an error without replacing the earlier decision.

## Manual completion report

Fill the supplied Word template and add your own screenshots and actual PR links. Export your reviewed final PDF to `docs/Visita-Domingo-EarlFrancis-G6-PD2.pdf`. Prepared report examples, old automatic capture/report scripts and screenshots remain local and ignored. When your own final report is ready, use the explicit report-staging instructions in GIT_WORKFLOW.md to include it in a PR into `develop`.

## Private upload storage and current limits

ID images are stored under ignored `media/private/`; PostgreSQL stores protected references/review metadata. There is no public media route. Only Administrators can download images, with private/no-store caching and attachment responses. Use fictional sample IDs for the lab. A deployed host needs durable private storage or a secure copy of the private directory. The ID list shows the newest 100 submissions; visits have pagination and status filtering. Successful workflow actions write audit records; an audit viewer is later work.

## Secrets and commits

`.env`, `.local/`, virtual environments, generated credentials, uploads and Python caches are ignored. If a database password has been shared, rotate it in Supabase and update only the private `.env`; it is separate from your Django account password. Debug mode is for local development.

Follow [GIT_WORKFLOW.md](GIT_WORKFLOW.md) for the exact two PD2 feature branches, file groups, commit messages, two PRs into `develop` and release PR into `main`. No automatic commits or pushes are made. Keep merged feature branches as the lab requires.
