#!/usr/bin/env python3
"""
PPDA Tender Scraper — Scrapes tenders from ppda.mw
Extracts procurement notices, intentions, and awards.
"""

import json
import os
import re
import sys
import hashlib
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

PPDA_URL = "https://www.ppda.mw/tenders"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

CONTENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'content', 'tenders')


def slugify(text):
    """Create URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:80].rstrip('-')


def parse_date(date_str):
    """Try to parse various date formats."""
    if not date_str:
        return None
    date_str = date_str.strip()

    formats = [
        '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d',
        '%d %B %Y', '%d %b %Y', '%B %d, %Y',
        '%d/%m/%y', '%d-%m-%y',
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None


def categorize_tender(title):
    """Guess category from title."""
    title_lower = title.lower()

    if any(w in title_lower for w in ['construction', 'building', 'road', 'bridge', 'renovation', 'infrastructure']):
        return 'works'
    if any(w in title_lower for w in ['consultancy', 'consultant', 'advisory', 'review', 'assessment', 'evaluation', 'study']):
        return 'consulting'
    if any(w in title_lower for w in ['software', 'ict', 'computer', 'system', 'digital', 'network', 'website']):
        return 'technology'
    if any(w in title_lower for w in ['medical', 'health', 'pharmaceutical', 'hospital', 'clinical']):
        return 'health'
    if any(w in title_lower for w in ['agriculture', 'farming', 'irrigation', 'fertilizer', 'seed', 'crop']):
        return 'agriculture'
    if any(w in title_lower for w in ['solar', 'energy', 'power', 'electricity', 'water supply', 'borehole']):
        return 'energy'
    if any(w in title_lower for w in ['vehicle', 'transport', 'logistics', 'freight', 'shipping']):
        return 'transport'
    if any(w in title_lower for w in ['training', 'education', 'workshop', 'capacity building']):
        return 'education'
    if any(w in title_lower for w in ['cleaning', 'security', 'catering', 'maintenance', 'repair']):
        return 'services'

    return 'goods'


def make_slug(entity, title, ref):
    """Create unique slug."""
    base = slugify(f"{title[:50]}-{entity[:20]}")
    if ref:
        base += f"-{slugify(ref[:15])}"
    return base


def scrape_ppda():
    """Scrape PPDA tenders page."""
    print(f"Fetching {PPDA_URL}...")

    try:
        r = requests.get(PPDA_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"Error fetching PPDA: {e}")
        return []

    soup = BeautifulSoup(r.text, 'lxml')
    tenders = []

    # Look for tables — PPDA uses DataTables
    tables = soup.find_all('table')

    for table in tables:
        table_id = table.get('id', '')
        rows = table.find_all('tr')

        # Determine table type from ID or headers
        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(['th', 'td'])] if rows else []

        is_tender_table = any(h in ' '.join(headers) for h in ['entity', 'tender', 'deadline', 'reference', 'closing'])
        if not is_tender_table and not table_id:
            continue

        print(f"  Found table '{table_id}' with {len(rows)-1} rows, headers: {headers}")

        for row in rows[1:]:  # Skip header
            cells = row.find_all('td')
            if len(cells) < 2:
                continue

            # Try to extract data — PPDA tables vary in structure
            cell_texts = [c.get_text(strip=True) for c in cells]

            # Find links (document URLs)
            doc_links = []
            for cell in cells:
                for a in cell.find_all('a', href=True):
                    href = a['href']
                    if href and not href.startswith('#') and not href.startswith('javascript'):
                        if not href.startswith('http'):
                            href = f"https://www.ppda.mw{href}"
                        doc_links.append({
                            'name': a.get_text(strip=True) or 'Document',
                            'url': href,
                            'type': 'pdf' if '.pdf' in href.lower() else 'link'
                        })

            # Map fields by header names (PPDA headers: title, institution, reference no., publish date, closing date, attachment)
            field_map = {}
            for i, h in enumerate(headers):
                if i < len(cell_texts):
                    field_map[h] = cell_texts[i]

            # Extract by header name, fall back to position
            title = field_map.get('title', cell_texts[0] if len(cell_texts) > 0 else '')
            entity_name = field_map.get('institution', field_map.get('entity', cell_texts[1] if len(cell_texts) > 1 else ''))
            reference = field_map.get('reference no.', field_map.get('reference', cell_texts[2] if len(cell_texts) > 2 else ''))
            deadline_str = field_map.get('closing date', field_map.get('deadline', cell_texts[4] if len(cell_texts) > 4 else cell_texts[3] if len(cell_texts) > 3 else ''))

            if not title or len(title) < 5:
                continue

            closing_date = parse_date(deadline_str)
            if not closing_date:
                # Default to 30 days from now if no date found
                closing_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

            slug = make_slug(entity_name, title, reference)
            entity_slug = slugify(entity_name) if entity_name else 'unknown-entity'

            tender = {
                'title': title,
                'slug': slug,
                'reference_number': reference,
                'source': 'ppda',
                'source_url': PPDA_URL,
                'procuring_entity': entity_name or 'Government of Malawi',
                'procuring_entity_slug': entity_slug,
                'entity_type': 'government',
                'tender_type': 'open',
                'procurement_method': 'open_competitive_bidding',
                'category': categorize_tender(title),
                'subcategories': [],
                'sectors': [categorize_tender(title)],
                'description_short': f"{title} — Procurement notice from {entity_name or 'Government of Malawi'}",
                'description_long': f"Procurement notice for {title}. Published by {entity_name or 'the Government of Malawi'} through the Public Procurement and Disposal of Assets Authority (PPDA).",
                'country': 'Malawi',
                'region': '',
                'city': '',
                'published_date': datetime.now().strftime('%Y-%m-%d'),
                'closing_date': closing_date,
                'closing_time': '',
                'estimated_value': None,
                'currency': 'MWK',
                'funding_source': 'government_budget',
                'donor': None,
                'document_urls': doc_links,
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

            tenders.append(tender)

    return tenders


def save_tenders(tenders):
    """Save tenders to JSON files."""
    os.makedirs(CONTENT_DIR, exist_ok=True)

    saved = 0
    skipped = 0

    for tender in tenders:
        filepath = os.path.join(CONTENT_DIR, f"{tender['slug']}.json")

        # Skip if already exists (idempotent)
        if os.path.exists(filepath):
            skipped += 1
            continue

        with open(filepath, 'w') as f:
            json.dump(tender, f, indent=2)
        saved += 1

    return saved, skipped


def main():
    print("=" * 60)
    print("PPDA TENDER SCRAPER")
    print("=" * 60)

    tenders = scrape_ppda()

    if not tenders:
        print("\nNo tenders found. PPDA page may have changed structure.")
        print("Skipping — will not create fake data.")
        return

    print(f"\nFound {len(tenders)} tenders")

    saved, skipped = save_tenders(tenders)
    print(f"Saved: {saved} | Skipped (already exists): {skipped}")
    print(f"Content dir: {CONTENT_DIR}")


if __name__ == '__main__':
    main()
