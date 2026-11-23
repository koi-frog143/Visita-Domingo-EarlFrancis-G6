"""Read-only browser regression checks; screenshots remain under ignored .local/.

Start Django, run seed_pd2 once, then: python scripts/check_ui.py
This signs in with dedicated test accounts and checks existing pages. It does
not create requests, upload IDs, edit profiles or generate completion evidence.
"""
import argparse
import json
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://127.0.0.1:8001")
args = parser.parse_args()
BASE = args.base_url.rstrip("/")
credentials = json.loads((ROOT / ".local/pd2-test-accounts.json").read_text(encoding="utf-8"))
OUT = ROOT / ".local/ui-regression"
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    js_errors = []
    checked = []
    page.on("pageerror", lambda error: js_errors.append(str(error)))

    def check(route, section, label, name):
        response = page.goto(BASE + route)
        assert response.status == 200, (route, response.status)
        page.evaluate("document.fonts.ready")
        active = page.locator(".sidebar-nav a.is-active")
        current = page.locator('.sidebar-nav a[aria-current="page"]')
        expect(active).to_have_count(1)
        expect(current).to_have_count(1)
        expect(active).to_have_attribute("href", section)
        expect(current).to_have_attribute("href", section)
        owner = "Administration" if role == "ADMIN" else "My space"
        expect(page.locator(".breadcrumb")).to_have_text(re.compile(r"^" + re.escape(owner) + r"\s*/\s*" + re.escape(label) + r"$"))
        for viewport, suffix in [({"width": 1440, "height": 1000}, "desktop"), ({"width": 393, "height": 852}, "mobile")]:
            page.set_viewport_size(viewport)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (name, suffix)
            images = page.locator("img").evaluate_all("""images => images.filter(i => i.getClientRects().length).map(i => ({src:i.getAttribute('src'),ok:i.complete && i.naturalWidth>0,w:i.getBoundingClientRect().width,h:i.getBoundingClientRect().height,nw:i.naturalWidth,nh:i.naturalHeight}))""")
            for item in images:
                assert item["ok"] and item["src"].startswith("/static/"), item
                assert abs(item["w"]/item["h"]-item["nw"]/item["nh"]) < .03, item
            checked.append(f"{name}-{suffix}")
        if name.endswith("dashboard") or name == "visitor-ids":
            page.screenshot(path=str(OUT / f"{name}-mobile.png"), full_page=True)
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
        page.set_viewport_size({"width": 1440, "height": 1000})
        print(f"PASS {name} (desktop/mobile)", flush=True)

    for role in ["VISITOR", "RESIDENT", "ADMIN", "GUARD"]:
        page.goto(BASE + "/accounts/login/")
        page.locator("[name=username]").fill(credentials[role]["email"])
        page.locator("[name=password]").fill(credentials[role]["password"])
        page.get_by_role("button", name="Log in", exact=True).click()
        page.wait_for_url(BASE + f"/dashboard/{role.lower()}/")
        check(f"/dashboard/{role.lower()}/", "/dashboard/", "Dashboard", f"{role.lower()}-dashboard")
        check("/accounts/profile/", "/accounts/profile/", "My profile", f"{role.lower()}-profile")
        check("/accounts/profile/edit/", "/accounts/profile/", "My profile", f"{role.lower()}-profile-edit")
        if role != "GUARD":
            check("/visits/", "/visits/", "Visit requests", f"{role.lower()}-visits")
            details = page.locator('.visit-table a[href^="/visits/"]').first
            if details.count():
                detail_url = details.get_attribute("href")
                check(detail_url, "/visits/", "Visit requests", f"{role.lower()}-visit-detail")
        if role == "VISITOR":
            check("/visits/new/", "/visits/", "Visit requests", "visitor-new-request")
            check("/visits/ids/", "/visits/ids/", "My ID submissions", "visitor-ids")
            check("/visits/ids/upload/", "/visits/ids/", "My ID submissions", "visitor-id-upload")
        elif role == "ADMIN":
            check("/visits/ids/", "/visits/ids/", "ID review", "admin-ids")
            review = page.locator('.visit-table a[href$="/review/"]').first
            if review.count():
                check(review.get_attribute("href"), "/visits/ids/", "ID review", "admin-id-review")
        if role in ["RESIDENT", "GUARD"]:
            assert page.goto(BASE + "/visits/ids/").status == 403
        if role == "GUARD":
            assert page.goto(BASE + "/visits/").status == 403
        if role != "ADMIN":
            assert page.goto(BASE + "/dashboard/admin/").status == 403
        page.get_by_role("button", name="Log out", exact=True).click()
        page.wait_for_url(BASE + "/accounts/login/")
    assert not js_errors, js_errors
    (OUT / "results.json").write_text(json.dumps({"checks": checked, "javascript_errors": js_errors}, indent=2), encoding="utf-8")
    browser.close()
print(f"All {len(checked)} browser checks passed; no business records changed.", flush=True)
