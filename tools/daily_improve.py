#!/usr/bin/env python3
"""
TendersMW Daily Improvement Script
Runs daily to keep the site fresh and growing without manual intervention.

Tasks:
1. Refresh tender statuses (mark expired tenders as closed)
2. Update closing dates and days_remaining
3. Generate daily stats summary
4. Submit new/changed URLs to IndexNow

Cron: 0 10 * * * cd /srv/BusinessOps/tendersmw && /srv/BusinessOps/.venv/bin/python3 tools/daily_improve.py >> /tmp/tendersmw_daily.log 2>&1
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CONTENT_DIR = BASE_DIR / "src" / "content" / "tenders"
DIST_DIR = BASE_DIR / "dist"

TELEGRAM_TOKEN = "8552358080:AAFC8FjKxQdj_NJyqwMbgUZrxKzUrn83tGY"
TELEGRAM_CHAT_ID = "1351661181"


def send_telegram(msg):
    """Send a message to Telegram."""
    import requests
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception:
        pass


def refresh_tender_statuses():
    """Update is_active, status, and days_remaining based on closing_date."""
    now = datetime.now()
    updated = 0
    newly_closed = 0
    total = 0
    active = 0

    for fp in sorted(CONTENT_DIR.glob("*.json")):
        total += 1
        try:
            with open(fp) as f:
                tender = json.load(f)

            changed = False
            closing_str = tender.get("closing_date", "")
            if closing_str:
                try:
                    closing = datetime.strptime(closing_str, "%Y-%m-%d")
                    is_active = closing > now
                    days_rem = max(0, (closing - now).days) if is_active else 0

                    if tender.get("is_active") != is_active:
                        if tender.get("is_active") and not is_active:
                            newly_closed += 1
                        tender["is_active"] = is_active
                        tender["status"] = "open" if is_active else "closed"
                        changed = True

                    if tender.get("days_remaining") != days_rem:
                        tender["days_remaining"] = days_rem
                        changed = True

                    if is_active:
                        active += 1
                except ValueError:
                    pass

            # Update last_updated
            if changed:
                tender["last_updated"] = now.strftime("%Y-%m-%d")
                with open(fp, "w") as f:
                    json.dump(tender, f, indent=2)
                updated += 1

        except Exception as e:
            print(f"  Error processing {fp.name}: {e}")

    return total, active, updated, newly_closed


def get_site_stats():
    """Get current site statistics."""
    stats = {"total": 0, "active": 0, "closed": 0, "sources": {}, "categories": {}}

    for fp in CONTENT_DIR.glob("*.json"):
        try:
            with open(fp) as f:
                t = json.load(f)
            stats["total"] += 1
            if t.get("is_active"):
                stats["active"] += 1
            else:
                stats["closed"] += 1
            src = t.get("source", "unknown")
            stats["sources"][src] = stats["sources"].get(src, 0) + 1
            cat = t.get("category", "unknown")
            stats["categories"][cat] = stats["categories"].get(cat, 0) + 1
        except Exception:
            pass

    return stats


def build_and_push():
    """Build the site and push if there are changes."""
    os.chdir(str(BASE_DIR))

    # Check for changes
    result = subprocess.run(
        ["git", "status", "--porcelain", "src/content/tenders/"],
        capture_output=True, text=True, cwd=str(BASE_DIR)
    )
    if not result.stdout.strip():
        print("  No changes to commit")
        return False

    changed_files = len(result.stdout.strip().split("\n"))
    print(f"  {changed_files} files changed, building...")

    # Build
    build = subprocess.run(
        ["npm", "run", "build"],
        capture_output=True, text=True, cwd=str(BASE_DIR), timeout=120
    )
    if build.returncode != 0:
        print(f"  Build failed: {build.stderr[:200]}")
        return False

    # Count pages
    page_count = 0
    for root, dirs, files in os.walk(str(DIST_DIR)):
        for f in files:
            if f == "index.html":
                page_count += 1

    print(f"  Build OK — {page_count} pages")

    # Commit and push
    subprocess.run(["git", "add", "src/content/tenders/"], cwd=str(BASE_DIR))
    subprocess.run(
        ["git", "commit", "-m", f"Daily refresh: update tender statuses ({page_count} pages)"],
        capture_output=True, text=True, cwd=str(BASE_DIR)
    )
    push = subprocess.run(
        ["git", "push", "origin", "main"],
        capture_output=True, text=True, cwd=str(BASE_DIR), timeout=60
    )
    if push.returncode != 0:
        print(f"  Push failed: {push.stderr[:200]}")
        return False

    print("  Pushed to origin/main")
    return True


def submit_indexnow():
    """Submit changed URLs to IndexNow."""
    import requests

    urls = []
    for root, dirs, files in os.walk(str(DIST_DIR)):
        for f in files:
            if f == "index.html":
                rel = os.path.relpath(root, str(DIST_DIR))
                url = "https://tendersmw.com/" if rel == "." else f"https://tendersmw.com/{rel}/"
                urls.append(url)

    if not urls:
        return 0

    payload = {
        "host": "tendersmw.com",
        "key": "f2018aa106044007bf54b7cde9067a1e",
        "urlList": urls[:10000],
    }
    try:
        r = requests.post(
            "https://api.indexnow.org/indexnow",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        print(f"  IndexNow: {r.status_code} ({len(urls)} URLs)")
        return len(urls)
    except Exception as e:
        print(f"  IndexNow error: {e}")
        return 0


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n{'='*60}")
    print(f"TendersMW Daily Improvement — {today}")
    print(f"{'='*60}")

    # 1. Refresh statuses
    print("\n[1] Refreshing tender statuses...")
    total, active, updated, newly_closed = refresh_tender_statuses()
    print(f"  Total: {total} | Active: {active} | Updated: {updated} | Newly closed: {newly_closed}")

    # 2. Build and push if changes
    pushed = False
    if updated > 0:
        print("\n[2] Building and pushing...")
        pushed = build_and_push()
    else:
        print("\n[2] No status changes, skipping build")

    # 3. Submit to IndexNow if pushed
    if pushed:
        print("\n[3] Submitting to IndexNow...")
        submit_indexnow()
    else:
        print("\n[3] Skipping IndexNow (no push)")

    # 4. Stats summary
    print("\n[4] Site stats...")
    stats = get_site_stats()
    print(f"  Tenders: {stats['total']} ({stats['active']} active, {stats['closed']} closed)")
    print(f"  Sources: {stats['sources']}")
    print(f"  Categories: {stats['categories']}")

    # 5. Telegram summary
    msg = (
        f"<b>TendersMW Daily — {today}</b>\n"
        f"Tenders: {stats['total']} ({stats['active']} active)\n"
        f"Sources: {', '.join(f'{k}:{v}' for k,v in stats['sources'].items())}\n"
    )
    if newly_closed > 0:
        msg += f"Newly closed: {newly_closed}\n"
    if updated > 0:
        msg += f"Statuses refreshed: {updated}\n"
    if pushed:
        msg += "Site rebuilt & pushed\n"

    send_telegram(msg)
    print(f"\n  Telegram summary sent")
    print(f"\n{'='*60}")
    print(f"TendersMW Daily Improvement — DONE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
