# Push the account refinements from your clone

Use **this cloned repository**: `~/Desktop/Visita/Visita-Domingo-EarlFrancis-G6`.

The existing branch is `feature/account-foundation`. Keep it; do not create the same branch again. Its GitHub origin and commit history have been preserved. No commits or pushes were made automatically.

## 1. Account validation and regression tests

```bash
cd ~/Desktop/Visita/Visita-Domingo-EarlFrancis-G6
git switch feature/account-foundation
git status
git add accounts/forms.py accounts/models.py accounts/views.py accounts/tests.py accounts/migrations/0002_alter_customuser_phone.py
git diff --cached
git commit -m "fix: strengthen Visita account validation"
git push -u origin feature/account-foundation
```

This adds contact-number validation, safe handling of concurrent duplicate email submissions, explicit Visitor privilege restrictions, and consistent role-based login redirects. It includes regression tests and a migration that preserves existing users and credentials.

## 2. Cozy green interface on a separate branch

```bash
git switch main
git switch -c feature/cozy-green-ui
git add static/css/style.css static/figma templates/accounts/auth_base.html templates/home.html templates/partials/form_field.html README.md GIT_WORKFLOW.md scripts
git diff --cached --stat
git diff --cached
git commit -m "style: apply cozy green Visita theme"
git push -u origin feature/cozy-green-ui
```

This preserves the existing layouts and changes their colors to forest green, sage, and cream, including the local SVG assets. The welcome text focuses on visits. Form help and error IDs support accessible validation messages. The `scripts` folder starts/stops only this prepared copy's private local PostgreSQL cluster; fresh clones should follow README's normal PostgreSQL setup.

## Pull request

Open two separate pull requests into `main`: `feature/account-foundation` for account validation and `feature/cozy-green-ui` for styling. The remaining uncommitted UI files carry over when switching from the account branch to main; only add the listed files to each commit.

**Title:** Refine Visita accounts and apply cozy green styling

**Description:** Improve registration and profile validation, handle concurrent duplicate emails, and direct each account to its authorized dashboard after login. Preserve the existing Django/PostgreSQL app, roles and migration history while applying forest green, sage and cream styling inspired by Haruhay.

Run the checks in README before merging. `.env`, `.local/`, virtual environments, database backups and passwords stay out of Git. Review `git status` before each commit.

After merging, start the next feature from updated main:

```bash
git switch main
git pull --ff-only origin main
git switch -c feature/visit-requests
```

Commit and push working changes as you complete them. Visit requests, approvals, check-in/out and history are later features; do not backdate or manufacture progress commits.
