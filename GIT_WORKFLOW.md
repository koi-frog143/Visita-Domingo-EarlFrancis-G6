# Finish the PD2 dashboard integration manually

The first feature is already merged into `develop` through [PR #7](https://github.com/koi-frog143/Visita-Domingo-EarlFrancis-G6/pull/7), from `feature/visit-request-workflow-corrected`. The earlier accidental merge into `main` was reverted through PR #6. Keep these history records and the feature branches.

Your current branch is **`feature/visit-dashboard-integration`**. It already exists. Continue here without creating the first feature branch again. The dashboard integration and fixes below are uncommitted; no commits or pushes were made by the assistant.

Run commands one at a time in Git Bash or PowerShell from this repository. If a command fails, stop and inspect its output before continuing.

## 1. Review and commit the application changes

This group includes role dashboard links/counts, exact sidebar and breadcrumb selection, unavailable-action guards, visible ID-review errors, regression tests, and test utilities. Completion evidence is excluded.

```bash
git branch --show-current
git status --short
git add config/settings.py core/context_processors.py core/views.py core/tests.py templates/base.html templates/partials/sidebar.html templates/dashboards/admin.html templates/dashboards/resident.html templates/dashboards/visitor.html templates/visits/detail.html templates/visits/review.html visits/views.py visits/tests.py scripts/check_ui.py scripts/verify_pd2.py requirements-dev.txt
git diff --cached --stat
git diff --cached
git commit -m "feat: integrate visit dashboards and fix workflow navigation"
```

## 2. Commit setup and workflow documentation

The ignore rules retain the prepared report examples and screenshots locally. The README describes the application and testing without linking to those uncommitted examples.

```bash
git add .gitignore README.md GIT_WORKFLOW.md
git diff --cached --stat
git commit -m "docs: update setup and manual PD2 submission workflow"
git push -u origin feature/visit-dashboard-integration
```

Create a pull request with:

- **Base:** `develop`
- **Compare:** `feature/visit-dashboard-integration`
- **Title:** `Integrate visit dashboards and fix workflow navigation`

Suggested description:

> The Visitor dashboard previously selected both Dashboard and Visit requests because navigation matched route-name fragments. Sidebar and breadcrumb labels now share exact route groups, with one active item per page across all roles. Role dashboards expose working request/ID links and scoped counts. Expired or stale workflow actions now show their current availability, repeated ID-review errors remain visible, and a request deleted during a resident decision returns 404. Includes regression tests and a read-only desktop/mobile browser check. Completion reports and evidence are prepared manually by the student.

Review the PR and merge it into **`develop`** with **Create a merge commit**. Keep the feature branch.

## 3. Prepare your own completion report

Fill the original Word template yourself, insert your own screenshots and validation example, and export the final PDF as:

`docs/Visita-Domingo-EarlFrancis-G6-PD2.pdf`

The previously prepared examples remain on your computer and are ignored by Git. They are not part of the dashboard commit. Once you have replaced the example PDF with your reviewed, manually completed version, explicitly stage only your final report:

```bash
git add -f docs/Visita-Domingo-EarlFrancis-G6-PD2.pdf
git diff --cached --stat
git commit -m "docs: add manually completed PD2 report"
git push
```

Do this on the dashboard branch while its PR is still open, or use a separate branch from the updated `develop` if the dashboard PR has already merged. Route that separate report PR into `develop` too. After the final PDF is tracked, later updates can use ordinary `git add`.

Use PR #7 for the first feature and the actual dashboard PR URL for the second feature. You can create a draft release PR with **base `main`**, **compare `develop`** to obtain its URL before finishing the report. Record actual statuses accurately; an open PR is not merged.

## 4. Release develop into main

After the dashboard PR and your final report are merged into `develop`:

```bash
git switch develop
git pull --ff-only origin develop
git status --short
```

Review the application and report. Create, or mark ready, the release PR with **base `main`**, **compare `develop`**. Title: **Release PD2 visit request and resident approval vertical slice**. Merge it with a merge commit and keep the feature branches and `develop`.

```bash
git switch main
git pull --ff-only origin main
git status --short
```

Submit your manually completed PDF and repository link to the lab. Keep `.env`, `.local/`, private media, backups and personal credentials out of Git. Use the explicit file groups above rather than `git add .`.
