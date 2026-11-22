# Push the integrity fix and documentation separately

Work in `~/Desktop/Visita/Visita-Domingo-EarlFrancis-G6`. The first branch, `fix/account-role-integrity`, is prepared locally. All edits are uncommitted. Your existing remote and main history are preserved.

## 1. Account integrity

Branch: `fix/account-role-integrity`

Description: Enforce the four valid account roles, block incompatible role/profile changes, validate profile saves and preserve credentials. Add a migration preflight and regression tests.

```bash
cd ~/Desktop/Visita/Visita-Domingo-EarlFrancis-G6
git switch fix/account-role-integrity
git add accounts/models.py accounts/tests.py accounts/migrations/0003_validate_roles_and_profiles.py
git diff --cached
git commit -m "fix: enforce account role and profile integrity"
git push -u origin fix/account-role-integrity
```

Open a pull request into `main` titled **Enforce account role and profile integrity**. Applying this feature to Supabase requires `manage.py migrate`; back up the database first. No Supabase migration or account reset was run automatically.

## 2. Setup instructions and SDD

Branch: `docs/django-setup-and-sdd`

Description: Restore installation, Supabase connection, run and testing instructions. Align the SDD with full-stack Django templates and PostgreSQL/Supabase while retaining its later-phase visitor workflows.

After committing the code fix, the remaining uncommitted documentation carries over when switching branches:

```bash
git switch main
git switch -c docs/django-setup-and-sdd
git add README.md GIT_WORKFLOW.md docs/Domingo-EarlFrancis-SDD.pdf
git diff --cached --stat
git commit -m "docs: restore setup guide and align SDD with Django"
git push -u origin docs/django-setup-and-sdd
```

Open another pull request into `main` titled **Restore setup guide and align SDD with Django**. Merge both PRs before following the integrity-update instructions. Your original Downloads PDF is preserved; the revised PDF is in this repository's `docs` folder.

Review `git status` before every commit. Never add private `.env`, `.local` contents or database backups. Rotate the database password previously shared in chat privately in Supabase if not already changed; it is not stored in either commit.
