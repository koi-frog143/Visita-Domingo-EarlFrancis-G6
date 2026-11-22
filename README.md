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
