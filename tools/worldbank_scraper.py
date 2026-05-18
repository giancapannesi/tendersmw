#!/usr/bin/env python3
"""
World Bank Procurement Scraper — Fetches Malawi tenders from WB Procurement API.
API: https://search.worldbank.org/api/v2/procnotices
Free, no auth required. 6,500+ Malawi notices available.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta
from html import unescape

import requests

CONTENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'content', 'tenders')

WB_API_URL = "https://search.worldbank.org/api/v2/procnotices"
HEADERS = {'User-Agent': 'TendersMW/1.0 (procurement aggregator)'}


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:80].rstrip('-')


def clean_html(text):
    text = re.sub(r'<[^>]+>', ' ', text)
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def categorize_tender(title):
    title_lower = title.lower()
    if any(w in title_lower for w in ['construction', 'building', 'road', 'bridge', 'infrastructure', 'rehabilitation']):
        return 'works'
    if any(w in title_lower for w in ['consultancy', 'consultant', 'advisory', 'evaluation', 'study', 'technical assistance', 'expression of interest']):
        return 'consulting'
    if any(w in title_lower for w in ['software', 'ict', 'computer', 'system', 'digital', 'network']):
        return 'technology'
    if any(w in title_lower for w in ['medical', 'health', 'pharmaceutical', 'hospital', 'nutrition']):
        return 'health'
    if any(w in title_lower for w in ['agriculture', 'farming', 'irrigation', 'fertilizer', 'food', 'seed', 'crop']):
        return 'agriculture'
    if any(w in title_lower for w in ['solar', 'energy', 'power', 'electricity', 'water supply', 'hydropower']):
        return 'energy'
    if any(w in title_lower for w in ['vehicle', 'transport', 'logistics', 'freight']):
        return 'transport'
    if any(w in title_lower for w in ['training', 'education', 'workshop', 'capacity building']):
        return 'education'
    return 'goods'


def fetch_worldbank_tenders(max_pages=3):
    """Fetch Malawi tenders from World Bank API. Only open notices (not contract awards)."""
    tenders = []
    rows_per_page = 50

    open_types = [
        'Invitation for Bids',
        'Request for Expression of Interest',
        'Request for Proposal',
        'Request for Quotation',
        'Prequalification',
    ]

    for notice_type in open_types:
        for page in range(max_pages):
            params = {
                'format': 'json',
                'qterm': 'Malawi',
                'notice_type_exact': notice_type,
                'rows': rows_per_page,
                'os': page * rows_per_page,
                'srt': 'submission_date',
                'order': 'desc',
            }

            try:
                r = requests.get(WB_API_URL, params=params, headers=HEADERS, timeout=30)
                if r.status_code != 200:
                    print(f"  WB API returned {r.status_code} for {notice_type}")
                    break

                data = r.json()
                notices = data.get('procnotices', [])
                if not notices:
                    break

                print(f"  {notice_type} page {page+1}: {len(notices)} results")

                for n in notices:
                    tender = parse_wb_notice(n, notice_type)
                    if tender:
                        tenders.append(tender)

                if len(notices) < rows_per_page:
                    break

            except Exception as e:
                print(f"  Error fetching {notice_type}: {e}")
                break

    return tenders


def parse_wb_notice(notice, notice_type):
    """Parse a World Bank API notice into our tender format."""
    try:
        title_raw = notice.get('notice_text', '')
        title = clean_html(title_raw)

        if not title or len(title) < 10:
            return None

        # Skip if not actually about Malawi
        title_and_project = (title + ' ' + notice.get('project_name', '')).lower()
        if 'malawi' not in title_and_project:
            return None

        # Skip contract awards — we only want open opportunities
        if notice_type == 'Contract Award':
            return None

        ref = notice.get('id', '')
        project_name = notice.get('project_name', '')
        deadline_raw = notice.get('submission_date', '')
        deadline = deadline_raw[:10] if deadline_raw else ''

        # Skip if deadline is more than 7 days in the past
        if deadline:
            try:
                dl = datetime.strptime(deadline, '%Y-%m-%d')
                if dl < datetime.now() - timedelta(days=7):
                    return None
            except ValueError:
                pass

        # Use project name + notice type as a better title if the raw title is too messy
        if len(title) > 200 or title.count('  ') > 3:
            title = f"{project_name} — {notice_type}"

        # Truncate very long titles
        if len(title) > 150:
            title = title[:147] + '...'

        notice_url = f"https://projects.worldbank.org/en/projects-operations/procurement-detail/{ref}"

        slug = slugify(f"wb-{project_name[:30]}-{ref}")
        category = categorize_tender(title + ' ' + project_name)
        entity = 'World Bank / Government of Malawi'

        return {
            'title': title,
            'slug': slug,
            'reference_number': ref,
            'source': 'world_bank',
            'source_url': notice_url,
            'procuring_entity': entity,
            'procuring_entity_slug': 'world-bank-government-of-malawi',
            'entity_type': 'international',
            'tender_type': notice_type.lower().replace(' ', '_'),
            'procurement_method': 'open_competitive_bidding',
            'category': category,
            'subcategories': [],
            'sectors': [category],
            'description_short': f"{project_name} — {notice_type}",
            'description_long': f"World Bank funded procurement for {project_name}. {notice_type} published through the World Bank procurement system. Reference: {ref}.",
            'country': 'Malawi',
            'region': '',
            'city': '',
            'published_date': datetime.now().strftime('%Y-%m-%d'),
            'closing_date': deadline,
            'closing_time': '',
            'estimated_value': None,
            'currency': 'USD',
            'funding_source': 'donor',
            'donor': 'World Bank',
            'document_urls': [{'name': 'World Bank Notice', 'url': notice_url, 'type': 'link'}],
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
    print("WORLD BANK TENDER SCRAPER — Malawi")
    print("=" * 60)

    tenders = fetch_worldbank_tenders()
    print(f"\nFound {len(tenders)} open Malawi tenders")

    if tenders:
        saved, skipped = save_tenders(tenders)
        print(f"Saved: {saved} | Skipped (already exists): {skipped}")
    else:
        print("No open Malawi tenders found from World Bank API.")

    print(f"Content dir: {CONTENT_DIR}")


if __name__ == '__main__':
    main()
