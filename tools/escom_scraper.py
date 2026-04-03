#!/usr/bin/env python3
"""
ESCOM Tender Scraper — Fetches tenders from Electricity Supply Corporation of Malawi.
Source: https://www.escom.mw/tenders/
Tech: WordPress + TablePress plugin, static HTML table (#tablepress-4)
SSL: Self-signed cert — uses verify=False
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

CONTENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'content', 'tenders')

ESCOM_URL = "https://www.escom.mw/tenders/"
HEADERS = {
    'User-Agent': 'TendersMW/1.0 (procurement aggregator)',
    'Accept': 'text/html',
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


def parse_date(date_str):
    """Parse inconsistent ESCOM date formats like '2nd January 2026 10:00 am'."""
    if not date_str:
        return None
    # Remove ordinal suffixes
    cleaned = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
    # Remove time-related noise
    cleaned = re.sub(r'\s*(at|hrs|hours?)\s*', ' ', cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip()

    for fmt in [
        '%d %B %Y %I:%M %p',
        '%d %B %Y %H:%M',
        '%d %B %Y',
        '%d %b %Y %I:%M %p',
        '%d %b %Y',
        '%B %d, %Y',
        '%d/%m/%Y',
    ]:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def categorize_tender(title):
    title_lower = title.lower()
    if any(w in title_lower for w in ['construction', 'building', 'road', 'bridge', 'infrastructure']):
        return 'works'
    if any(w in title_lower for w in ['consultancy', 'consultant', 'advisory', 'evaluation', 'study', 'technical assistance']):
        return 'consulting'
    if any(w in title_lower for w in ['software', 'ict', 'computer', 'system', 'digital', 'network', 'hyperconverged']):
        return 'technology'
    if any(w in title_lower for w in ['transformer', 'cable', 'meter', 'electrical', 'power', 'energy', 'solar', 'electricity', 'substation']):
        return 'energy'
    if any(w in title_lower for w in ['vehicle', 'transport', 'logistics', 'fleet']):
        return 'transport'
    if any(w in title_lower for w in ['cleaning', 'security', 'catering', 'maintenance']):
        return 'services'
    if any(w in title_lower for w in ['medical', 'health']):
        return 'health'
    return 'goods'


def fetch_escom_tenders():
    """Scrape tenders from ESCOM website."""
    tenders = []

    try:
        print("Fetching from ESCOM...")
        r = requests.get(ESCOM_URL, headers=HEADERS, timeout=30, verify=False)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', id='tablepress-4')

        if not table:
            # Try any tablepress table
            table = soup.find('table', class_=re.compile(r'tablepress'))

        if not table:
            print("  No tender table found on ESCOM page")
            return tenders

        tbody = table.find('tbody')
        if not tbody:
            print("  No tbody in table")
            return tenders

        rows = tbody.find_all('tr')
        print(f"  Found {len(rows)} rows")

        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 3:
                continue

            # Extract text from each cell (content may be wrapped in <a> tags)
            name = cells[0].get_text(strip=True)
            description = cells[1].get_text(strip=True) if len(cells) > 1 else ''
            closing_str = cells[2].get_text(strip=True) if len(cells) > 2 else ''

            # Get document download link
            doc_link = None
            if len(cells) > 3:
                a_tag = cells[3].find('a', href=True)
                if a_tag:
                    doc_link = a_tag['href']
                    if doc_link.startswith('/'):
                        doc_link = f"https://www.escom.mw{doc_link}"

            # Skip rows that are just addendums or corrigenda with no real title
            if not name or len(name) < 5:
                continue
            # Use description as title if name is too short
            title = name if len(name) > 15 else f"{name}: {description}" if description else name
            title = title.strip()

            if not title or len(title) < 5:
                continue

            # Parse closing date
            closing_date = parse_date(closing_str)
            closing_date_str = closing_date.strftime('%Y-%m-%d') if closing_date else ''

            # Determine if active
            is_active = True
            if closing_date and closing_date < datetime.now():
                is_active = False

            slug = slugify(f"escom-{title[:50]}")
            category = categorize_tender(title)

            tender = {
                'title': title,
                'slug': slug,
                'reference_number': f"ESCOM-{slugify(name[:30])}",
                'source': 'escom',
                'source_url': ESCOM_URL,
                'procuring_entity': 'Electricity Supply Corporation of Malawi (ESCOM)',
                'procuring_entity_slug': 'electricity-supply-corporation-of-malawi-escom',
                'entity_type': 'parastatal',
                'tender_type': 'open',
                'procurement_method': 'open_competitive_bidding',
                'category': category,
                'subcategories': [],
                'sectors': [category, 'energy'],
                'description_short': f"{title}",
                'description_long': description if description else f"Procurement notice from ESCOM: {title}",
                'country': 'Malawi',
                'region': '',
                'city': 'Blantyre',
                'published_date': datetime.now().strftime('%Y-%m-%d'),
                'closing_date': closing_date_str,
                'closing_time': '',
                'estimated_value': None,
                'currency': 'MWK',
                'funding_source': 'government',
                'donor': '',
                'document_urls': [{'name': 'Tender Document', 'url': doc_link, 'type': 'pdf'}] if doc_link else [],
                'contact_email': '',
                'contact_phone': '',
                'status': 'open' if is_active else 'closed',
                'is_active': is_active,
                'days_remaining': (closing_date - datetime.now()).days if closing_date and is_active else 0,
                'similar_tenders': [],
                'last_updated': datetime.now().strftime('%Y-%m-%d'),
                'review_status': 'published',
                'quality_score': 3,
                'has_been_enriched': False,
            }
            tenders.append(tender)

    except Exception as e:
        print(f"  Error fetching ESCOM: {e}")

    return tenders


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
    print("ESCOM TENDER SCRAPER")
    print("=" * 60)

    tenders = fetch_escom_tenders()
    print(f"\nFound {len(tenders)} tenders")

    if tenders:
        saved, skipped = save_tenders(tenders)
        print(f"Saved: {saved} | Skipped (already exists): {skipped}")
    else:
        print("No tenders found from ESCOM.")

    print(f"Content dir: {CONTENT_DIR}")


if __name__ == '__main__':
    main()
