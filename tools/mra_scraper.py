#!/usr/bin/env python3
"""
MRA Tender Scraper — Fetches tenders from Malawi Revenue Authority.
Source: https://www.mra.mw/tenders
Tech: React SPA with REST API backend
API: GET https://www.mra.mw/admin/api/v1/download/getAllTenders?per_page=100&page=1
Auth: Hardcoded client-side access token (not a secret — shipped in JS bundle)
SSL: Self-signed cert — uses verify=False
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta

import requests

CONTENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'content', 'tenders')

MRA_API_URL = "https://www.mra.mw/admin/api/v1/download/getAllTenders"
HEADERS = {
    'User-Agent': 'TendersMW/1.0 (procurement aggregator)',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'access-token': 'cbkjssjtyfu73928393nvjbvdsbshd',
}

# Suppress InsecureRequestWarning for verify=False
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:80].rstrip('-')


def categorize_tender(title):
    title_lower = title.lower()
    if any(w in title_lower for w in ['construction', 'building', 'road', 'bridge', 'infrastructure', 'renovation']):
        return 'works'
    if any(w in title_lower for w in ['consultancy', 'consultant', 'advisory', 'evaluation', 'study', 'technical assistance']):
        return 'consulting'
    if any(w in title_lower for w in ['software', 'ict', 'computer', 'system', 'digital', 'network', 'hyperconverged', 'server']):
        return 'technology'
    if any(w in title_lower for w in ['vehicle', 'transport', 'logistics', 'fleet', 'motor']):
        return 'transport'
    if any(w in title_lower for w in ['cleaning', 'security', 'catering', 'maintenance', 'guard']):
        return 'services'
    if any(w in title_lower for w in ['stationery', 'office', 'furniture', 'printing']):
        return 'goods'
    if any(w in title_lower for w in ['training', 'education', 'capacity']):
        return 'education'
    if any(w in title_lower for w in ['medical', 'health']):
        return 'health'
    return 'goods'


def parse_mra_date(date_str):
    """Parse MRA date format like '27 Mar 2026'."""
    if not date_str:
        return None
    for fmt in ['%d %b %Y', '%d %B %Y', '%Y-%m-%d']:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def fetch_mra_tenders():
    """Fetch tenders from MRA API."""
    tenders = []
    page = 1
    per_page = 100

    try:
        while True:
            print(f"Fetching MRA page {page}...")
            params = {'per_page': per_page, 'page': page}
            r = requests.get(MRA_API_URL, params=params, headers=HEADERS, timeout=30, verify=False)

            if r.status_code != 200:
                print(f"  MRA API returned {r.status_code}")
                break

            data = r.json()
            items = data.get('data', data) if isinstance(data, dict) else data
            if not items:
                break

            if isinstance(items, dict):
                # Might be nested
                items = items.get('data', [])

            print(f"  Got {len(items)} items")

            for item in items:
                tender = parse_mra_item(item)
                if tender:
                    tenders.append(tender)

            # Stop if fewer items than requested (last page)
            if len(items) < per_page:
                break

            page += 1
            if page > 10:  # Safety limit
                break

    except Exception as e:
        print(f"  Error fetching MRA: {e}")

    return tenders


def parse_mra_item(item):
    """Parse an MRA API response item into our tender format."""
    try:
        title = item.get('downloadFilename', '').strip()
        if not title or len(title) < 5:
            return None

        # Skip EU tender dossier templates (c4a, c4b, etc.) and non-tender documents
        title_lower = title.lower()
        skip_patterns = [
            'c4a_', 'c4b_', 'c4d_', 'c4k_', 'c4l_', 'c4o',
            'a5e_', 'a5f_', 'a11c_', 'a14a_',
            'lefind_en', 'lefcompany_en', 'lefpublic_en', 'fif_en',
            'contractnotice_enotices', 'specialconditions_en', 'evalgrid_en',
            'invit_en', 'itt_en', 'tenderform_en',
            'tax stamps regulation', 'tax incentives for the',
            'new tax measures for',
        ]
        if any(p in title_lower for p in skip_patterns):
            return None
        # Skip withdrawn/cancelled
        if title_lower.startswith('withdrawn') or title_lower.startswith('cancellation of'):
            return None

        item_id = item.get('id', '')
        pub_date_str = item.get('formatted_created_at', '')
        file_path = item.get('downloadFilePath', '')
        file_size = item.get('downloadFileSize', '')

        pub_date = parse_mra_date(pub_date_str)
        pub_date_iso = pub_date.strftime('%Y-%m-%d') if pub_date else datetime.now().strftime('%Y-%m-%d')

        # MRA doesn't provide closing dates — estimate 30 days from publication
        # For older tenders, mark as closed
        if pub_date:
            estimated_closing = pub_date + timedelta(days=30)
            is_active = estimated_closing > datetime.now()
            closing_date_str = estimated_closing.strftime('%Y-%m-%d')
            days_remaining = (estimated_closing - datetime.now()).days if is_active else 0
        else:
            is_active = True
            closing_date_str = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            days_remaining = 30

        slug = slugify(f"mra-{title[:50]}-{item_id}")
        category = categorize_tender(title)
        ref = f"MRA-{item_id}" if item_id else f"MRA-{slugify(title[:30])}"

        return {
            'title': title,
            'slug': slug,
            'reference_number': ref,
            'source': 'mra',
            'source_url': 'https://www.mra.mw/tenders',
            'procuring_entity': 'Malawi Revenue Authority (MRA)',
            'procuring_entity_slug': 'malawi-revenue-authority-mra',
            'entity_type': 'government',
            'tender_type': 'open',
            'procurement_method': 'open_competitive_bidding',
            'category': category,
            'subcategories': [],
            'sectors': [category],
            'description_short': title,
            'description_long': f"Procurement notice from Malawi Revenue Authority: {title}",
            'country': 'Malawi',
            'region': '',
            'city': 'Blantyre',
            'published_date': pub_date_iso,
            'closing_date': closing_date_str,
            'closing_time': '',
            'estimated_value': None,
            'currency': 'MWK',
            'funding_source': 'government',
            'donor': '',
            'document_urls': [{'name': 'Tender Document', 'url': file_path, 'type': 'pdf'}] if file_path else [],
            'contact_email': '',
            'contact_phone': '',
            'status': 'open' if is_active else 'closed',
            'is_active': is_active,
            'days_remaining': max(0, days_remaining),
            'similar_tenders': [],
            'last_updated': datetime.now().strftime('%Y-%m-%d'),
            'review_status': 'published',
            'quality_score': 3,
            'has_been_enriched': False,
        }
    except Exception as e:
        print(f"  Parse error: {e}")
        return None


def save_tenders(tenders):
    """Save tenders to JSON files."""
    os.makedirs(CONTENT_DIR, exist_ok=True)
    saved = 0
    skipped = 0

    for tender in tenders:
        filepath = os.path.join(CONTENT_DIR, f"{tender['slug']}.json")
        if os.path.exists(filepath):
            skipped += 1
            continue
        with open(filepath, 'w') as f:
            json.dump(tender, f, indent=2)
        saved += 1

    return saved, skipped


def main():
    print("=" * 60)
    print("MRA TENDER SCRAPER — Malawi Revenue Authority")
    print("=" * 60)

    tenders = fetch_mra_tenders()
    print(f"\nFound {len(tenders)} tenders")

    if tenders:
        saved, skipped = save_tenders(tenders)
        print(f"Saved: {saved} | Skipped (already exists): {skipped}")
    else:
        print("No tenders found from MRA API.")

    print(f"Content dir: {CONTENT_DIR}")


if __name__ == '__main__':
    main()
