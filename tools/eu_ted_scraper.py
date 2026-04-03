#!/usr/bin/env python3
"""
EU TED Tender Scraper — Fetches Malawi tenders from the EU's Tenders Electronic Daily API.
The EU has committed EUR 352M to Malawi (2021-2027).
API: https://ted.europa.eu/api (REST, no auth required)
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta

import requests

CONTENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'content', 'tenders')

# TED API endpoints
TED_SEARCH_URL = "https://ted.europa.eu/api/v3.0/notices/search"
HEADERS = {
    'User-Agent': 'TendersMW/1.0 (procurement aggregator)',
    'Accept': 'application/json',
}


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:80].rstrip('-')


def categorize_tender(title):
    title_lower = title.lower()
    if any(w in title_lower for w in ['construction', 'building', 'road', 'bridge', 'infrastructure']):
        return 'works'
    if any(w in title_lower for w in ['consultancy', 'consultant', 'advisory', 'evaluation', 'study', 'technical assistance']):
        return 'consulting'
    if any(w in title_lower for w in ['software', 'ict', 'computer', 'system', 'digital', 'network']):
        return 'technology'
    if any(w in title_lower for w in ['medical', 'health', 'pharmaceutical', 'hospital']):
        return 'health'
    if any(w in title_lower for w in ['agriculture', 'farming', 'irrigation', 'fertilizer']):
        return 'agriculture'
    if any(w in title_lower for w in ['solar', 'energy', 'power', 'electricity', 'water']):
        return 'energy'
    if any(w in title_lower for w in ['vehicle', 'transport', 'logistics']):
        return 'transport'
    if any(w in title_lower for w in ['training', 'education', 'capacity building']):
        return 'education'
    if any(w in title_lower for w in ['cleaning', 'security', 'catering', 'maintenance']):
        return 'services'
    return 'goods'


def fetch_ted_malawi():
    """Fetch Malawi-related tenders from EU TED API."""
    tenders = []

    # Search for Malawi in performance place
    params = {
        'q': 'malawi',
        'scope': 3,  # Contract notices
        'limit': 50,
        'sortField': 'publicationDate',
        'sortOrder': 'desc',
    }

    try:
        # Try the search API
        print("Fetching from TED API...")
        r = requests.get(TED_SEARCH_URL, params=params, headers=HEADERS, timeout=30)

        if r.status_code == 200:
            data = r.json()
            notices = data.get('notices', data.get('results', []))
            print(f"  Found {len(notices)} results")

            for notice in notices:
                tender = parse_ted_notice(notice)
                if tender:
                    tenders.append(tender)
        else:
            print(f"  TED API returned {r.status_code}")
            # Fallback: try v2 API
            tenders = fetch_ted_v2_fallback()

    except Exception as e:
        print(f"  Error: {e}")
        tenders = fetch_ted_v2_fallback()

    return tenders


def fetch_ted_v2_fallback():
    """Fallback to TED expert search."""
    tenders = []

    # Try TED expert search URL
    search_url = "https://ted.europa.eu/api/v2.0/notices/search"
    params = {
        'q': 'RC=[MW]',  # Country code for Malawi
        'scope': 3,
        'limit': 20,
    }

    try:
        r = requests.get(search_url, params=params, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            data = r.json()
            for notice in data.get('results', []):
                tender = parse_ted_notice(notice)
                if tender:
                    tenders.append(tender)
    except Exception as e:
        print(f"  v2 fallback error: {e}")

    return tenders


def parse_ted_notice(notice):
    """Parse a TED API notice into our tender format."""
    try:
        title = notice.get('title', {})
        if isinstance(title, dict):
            title = title.get('en', title.get('EN', next(iter(title.values()), '')))
        if isinstance(title, list):
            title = title[0] if title else ''

        if not title or len(str(title)) < 5:
            return None

        title = str(title).strip()

        # Extract fields
        notice_id = notice.get('noticeId', notice.get('tedNoticeId', ''))
        pub_date = notice.get('publicationDate', notice.get('datePublished', ''))
        deadline = notice.get('submissionDeadline', notice.get('deadlineDate', ''))

        # Entity
        entity = notice.get('buyerName', notice.get('contractingBody', ''))
        if isinstance(entity, dict):
            entity = entity.get('en', next(iter(entity.values()), ''))
        entity = str(entity).strip() or 'European Union Delegation'

        # Value
        value = notice.get('estimatedValue', notice.get('contractValue', None))
        currency = notice.get('currency', 'EUR')

        # Format dates
        if pub_date and 'T' in str(pub_date):
            pub_date = str(pub_date).split('T')[0]
        if deadline and 'T' in str(deadline):
            deadline = str(deadline).split('T')[0]

        if not deadline:
            deadline = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

        ref = str(notice_id) if notice_id else f"TED-{slugify(title[:30])}"
        slug = slugify(f"eu-{title[:50]}-{ref[:15]}")
        entity_slug = slugify(entity)
        category = categorize_tender(title)

        ted_url = f"https://ted.europa.eu/en/notice/-/detail/{notice_id}" if notice_id else "https://ted.europa.eu"

        return {
            'title': title,
            'slug': slug,
            'reference_number': ref,
            'source': 'eu_ted',
            'source_url': ted_url,
            'procuring_entity': entity,
            'procuring_entity_slug': entity_slug,
            'entity_type': 'international',
            'tender_type': 'open',
            'procurement_method': 'open_competitive_bidding',
            'category': category,
            'subcategories': [],
            'sectors': [category],
            'description_short': f"{title} — EU-funded procurement notice for Malawi",
            'description_long': f"European Union funded procurement: {title}. Published through Tenders Electronic Daily (TED). The EU has committed EUR 352 million to Malawi for the 2021-2027 programming period.",
            'country': 'Malawi',
            'region': '',
            'city': '',
            'published_date': pub_date or datetime.now().strftime('%Y-%m-%d'),
            'closing_date': deadline,
            'closing_time': '',
            'estimated_value': float(value) if value else None,
            'currency': currency,
            'funding_source': 'donor',
            'donor': 'European Union',
            'document_urls': [{'name': 'TED Notice', 'url': ted_url, 'type': 'link'}] if notice_id else [],
            'contact_email': '',
            'contact_phone': '',
            'status': 'open',
            'is_active': True,
            'days_remaining': 0,
            'similar_tenders': [],
            'last_updated': datetime.now().strftime('%Y-%m-%d'),
            'review_status': 'published',
            'quality_score': 4,
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
    print("EU TED TENDER SCRAPER — Malawi")
    print("=" * 60)

    tenders = fetch_ted_malawi()
    print(f"\nFound {len(tenders)} tenders")

    if tenders:
        saved, skipped = save_tenders(tenders)
        print(f"Saved: {saved} | Skipped (already exists): {skipped}")
    else:
        print("No tenders found from TED API. The API may have changed or no active Malawi notices.")

    print(f"Content dir: {CONTENT_DIR}")


if __name__ == '__main__':
    main()
