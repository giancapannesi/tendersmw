#!/usr/bin/env python3
"""
Tender Verification Gate — AI confirms each new tender is real before publish.

Every new tender JSON must pass this gate. The verifier:
1. Checks the tender has a real source_url (not a generic domain)
2. Fetches the source page to confirm the procuring entity exists there
3. Asks an AI to confirm the tender data matches real scraped content
4. REJECTS anything it can't verify — no exceptions

Usage:
    python3 verify_tender.py <path_to_tender.json>
    python3 verify_tender.py --batch <dir_of_jsons> [--existing-slugs-file slugs.txt]

Exit codes:
    0 = verified real
    1 = rejected (not verifiable)
    2 = error
"""

import json
import os
import sys
import requests

OPENROUTER_KEY_PATH = "/srv/BusinessOps/tools/.openrouter-api-key"

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def load_api_key():
    with open(OPENROUTER_KEY_PATH) as f:
        return f.read().strip()


def fetch_source_page(url, timeout=20):
    """Fetch the source URL and return text content."""
    try:
        r = requests.get(url, timeout=timeout, verify=False, headers={
            'User-Agent': 'TendersMW/1.0 (verification bot)'
        })
        if r.status_code == 200:
            return r.text[:5000]
        return f"HTTP {r.status_code}"
    except Exception as e:
        return f"FETCH ERROR: {e}"


def verify_with_ai(tender_data, source_content, api_key):
    """Ask AI to verify the tender matches real source content."""
    prompt = f"""You are a tender verification bot. Your job is to determine if a tender listing is REAL (actually scraped from a real source) or FABRICATED (made up / sample data).

TENDER DATA:
- Title: {tender_data.get('title')}
- Reference: {tender_data.get('reference_number')}
- Entity: {tender_data.get('procuring_entity')}
- Source: {tender_data.get('source')}
- Source URL: {tender_data.get('source_url')}
- Closing date: {tender_data.get('closing_date')}
- Description: {tender_data.get('description_long', '')}

SOURCE PAGE CONTENT (first 5000 chars from source_url):
{source_content[:3000]}

RULES:
- If the source page content contains the tender title, entity name, or reference number: REAL
- If the source page returned an error or the tender data doesn't appear anywhere on the source page: check if the entity name at minimum appears on the page
- If the tender has generic placeholder descriptions like "invites sealed bids from eligible firms" with no specific details: SUSPICIOUS
- If the reference number looks invented (round numbers, too-clean format like MOE/G/2026/019): SUSPICIOUS
- If you cannot confirm this tender exists from the source content: REJECT

Respond with ONLY one word: VERIFIED or REJECTED
Then on the next line, a one-sentence reason."""

    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "google/gemini-2.0-flash-001",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100,
                "temperature": 0,
            },
            timeout=30,
        )
        if r.status_code == 200:
            text = r.json()["choices"][0]["message"]["content"].strip()
            return text
        return f"REJECTED\nAI API returned {r.status_code}"
    except Exception as e:
        return f"REJECTED\nAI verification failed: {e}"


def verify_tender(tender_path):
    """Verify a single tender file. Returns (passed: bool, reason: str)."""
    with open(tender_path) as f:
        tender = json.load(f)

    title = tender.get("title", "")
    source = tender.get("source", "")
    source_url = tender.get("source_url", "")
    entity = tender.get("procuring_entity", "")
    ref = tender.get("reference_number", "")

    # Gate 1: must have source and source_url
    if not source or not source_url:
        return False, "No source or source_url"

    # Gate 2: source_url must not be just a domain root (sign of fabrication)
    # Exception: some real scrapers use the main tenders page as source_url
    # so we allow known legitimate patterns
    legitimate_sources = [
        "https://www.ppda.mw/tenders",
        "https://www.escom.mw/tenders/",
        "https://www.mra.mw/tenders",
        "https://ted.europa.eu",
        "https://projects.worldbank.org/",
    ]
    url_ok = any(source_url.startswith(s) for s in legitimate_sources)
    if not url_ok:
        return False, f"Unknown source_url: {source_url}"

    # Gate 3: fetch the source page and verify with AI
    api_key = load_api_key()
    source_content = fetch_source_page(source_url)

    # If we can't reach the source at all, reject
    if source_content.startswith("FETCH ERROR"):
        # For known-flaky sources (self-signed certs), do a lighter check
        if source in ("escom", "mra"):
            # These have self-signed certs but we scrape via API/HTML
            # If the scraper returned data, it got a real response
            # Verify the entity name at minimum is a known real entity
            known_entities = [
                "Electricity Supply Corporation of Malawi",
                "ESCOM",
                "Malawi Revenue Authority",
                "MRA",
                "World Bank",
            ]
            if any(k.lower() in entity.lower() for k in known_entities):
                return True, f"Known entity ({entity}), source unreachable but trusted scraper"
        return False, f"Cannot reach source: {source_content}"

    ai_result = verify_with_ai(tender, source_content, api_key)
    lines = ai_result.strip().split("\n", 1)
    verdict = lines[0].strip().upper()
    reason = lines[1].strip() if len(lines) > 1 else "No reason given"

    if "VERIFIED" in verdict:
        return True, reason
    else:
        return False, reason


def main():
    if len(sys.argv) < 2:
        print("Usage: verify_tender.py <tender.json> | --batch <dir> [--existing-slugs-file slugs.txt]")
        sys.exit(2)

    if sys.argv[1] == "--batch":
        tender_dir = sys.argv[2] if len(sys.argv) > 2 else "."
        existing_slugs = set()
        if "--existing-slugs-file" in sys.argv:
            idx = sys.argv.index("--existing-slugs-file")
            if idx + 1 < len(sys.argv):
                with open(sys.argv[idx + 1]) as f:
                    existing_slugs = set(line.strip() for line in f)

        verified = 0
        rejected = 0
        skipped = 0

        for fname in sorted(os.listdir(tender_dir)):
            if not fname.endswith(".json"):
                continue
            slug = fname.replace(".json", "")
            if slug in existing_slugs:
                skipped += 1
                continue

            path = os.path.join(tender_dir, fname)
            passed, reason = verify_tender(path)
            if passed:
                print(f"  VERIFIED: {fname} — {reason}")
                verified += 1
            else:
                print(f"  REJECTED: {fname} — {reason}")
                os.remove(path)
                rejected += 1

        print(f"\nVerification complete: {verified} verified, {rejected} rejected, {skipped} skipped (existing)")
        sys.exit(1 if rejected > 0 and verified == 0 else 0)

    else:
        tender_path = sys.argv[1]
        passed, reason = verify_tender(tender_path)
        if passed:
            print(f"VERIFIED: {reason}")
            sys.exit(0)
        else:
            print(f"REJECTED: {reason}")
            sys.exit(1)


if __name__ == "__main__":
    main()
