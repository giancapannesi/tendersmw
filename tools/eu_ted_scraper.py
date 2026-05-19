#!/usr/bin/env python3
"""
EU TED Tender Scraper — Fetches Malawi tenders from Tenders Electronic Daily (TED) v3 API.
The EU has committed EUR 352M to Malawi (2021-2027).

API: https://api.ted.europa.eu/v3/notices/search (POST, no auth required)
Strategy:
  1. Search for full-text "malawi" with recent publication date
  2. Fetch XML for each notice
  3. Filter: only keep notices where MWI is in location codes (not just text mentions)
  4. Only keep contract notices (cn-*) and prior information (pin-*), not awards (can-*)
  5. Parse title, entity, deadline from eForms XML
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta

import requests

CONTENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'content', 'tenders')

TED_SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"
TED_XML_URL = "https://ted.europa.eu/en/notice/{pub_num}/xml"
TED_HTML_URL = "https://ted.europa.eu/en/notice/-/detail/{pub_num}"
HEADERS = {'User-Agent': 'TendersMW/1.0 (procurement aggregator)'}

OPEN_NOTICE_TYPES = {'cn-standard', 'cn-social', 'cn-desg', 'pin-buyer', 'pin-cfc-standard',
                     'pin-cfc-social', 'pin-rtl', 'pin-tran', 'qu-sy', 'subco', 'veat'}


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:80].rstrip('-')


def categorize_tender(title):
    title_lower = title.lower()
    if any(w in title_lower for w in ['construction', 'building', 'road', 'bridge', 'infrastructure', 'rehabilitation']):
        return 'works'
    if any(w in title_lower for w in ['consultancy', 'consultant', 'advisory', 'evaluation', 'study', 'technical assistance']):
        return 'consulting'
    if any(w in title_lower for w in ['software', 'ict', 'computer', 'system', 'digital', 'network']):
        return 'technology'
    if any(w in title_lower for w in ['medical', 'health', 'pharmaceutical', 'hospital', 'nutrition']):
        return 'health'
    if any(w in title_lower for w in ['agriculture', 'farming', 'irrigation', 'fertilizer', 'food', 'seed']):
        return 'agriculture'
    if any(w in title_lower for w in ['solar', 'energy', 'power', 'electricity', 'water supply', 'hydropower']):
        return 'energy'
    if any(w in title_lower for w in ['vehicle', 'transport', 'logistics']):
        return 'transport'
    if any(w in title_lower for w in ['training', 'education', 'capacity building']):
        return 'education'
    return 'goods'


def search_ted_notices():
    """Search TED for Malawi-related notices published in last 90 days."""
    cutoff = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')
    try:
        r = requests.post(TED_SEARCH_URL, json={
            'query': f'FT~"malawi" AND PD>={cutoff}',
            'fields': ['BT-01-notice'],
            'page': 1,
            'limit': 100,
        }, headers={'Content-Type': 'application/json'}, timeout=30)

        if r.status_code != 200:
            print(f"  TED search returned {r.status_code}")
            return []

        data = r.json()
        notices = data.get('notices', [])
        pub_numbers = [n.get('publication-number') for n in notices if n.get('publication-number')]
        print(f"  Search returned {len(pub_numbers)} notices mentioning 'malawi'")
        return pub_numbers

    except Exception as e:
        print(f"  Search error: {e}")
        return []


def fetch_notice_xml(pub_num):
    """Fetch the eForms XML for a single notice."""
    try:
        r = requests.get(TED_XML_URL.format(pub_num=pub_num), headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r.text
        return None
    except Exception:
        return None


def parse_notice_xml(xml_text, pub_num):
    """Parse eForms XML into tender dict. Returns None if not a valid Malawi open tender."""
    location_codes = set(re.findall(r'<cbc:IdentificationCode[^>]*>([A-Z]{3})</cbc:IdentificationCode>', xml_text))
    if 'MWI' not in location_codes:
        return None

    type_match = re.search(r'<cbc:NoticeTypeCode[^>]*>([^<]+)', xml_text)
    notice_type = type_match.group(1) if type_match else ''
    if notice_type not in OPEN_NOTICE_TYPES:
        return None

    # Title — from ProcurementProject/Name (the project-level one, not lot-level)
    # ProcurementProject names appear after ProcurementProject tags
    proj_section = re.search(r'<cac:ProcurementProject>.*?</cac:ProcurementProject>', xml_text, re.DOTALL)
    title = ''
    if proj_section:
        proj_text = proj_section.group(0)
        eng_name = re.search(r'<cbc:Name\s+languageID="ENG"[^>]*>([^<]+)', proj_text)
        any_name = re.search(r'<cbc:Name[^>]*>([^<]+)', proj_text)
        title = (eng_name or any_name).group(1).strip() if (eng_name or any_name) else ''
    if not title or len(title) < 10:
        return None

    # Description — from ProcurementProject/Description
    description = ''
    if proj_section:
        eng_desc = re.search(r'<cbc:Description\s+languageID="ENG"[^>]*>([^<]+)', proj_section.group(0))
        any_desc = re.search(r'<cbc:Description[^>]*>([^<]+)', proj_section.group(0))
        description = (eng_desc or any_desc).group(1).strip() if (eng_desc or any_desc) else ''
    if not description:
        desc_matches = re.findall(r'<cbc:Description\s+languageID="ENG"[^>]*>([^<]+)', xml_text)
        description = desc_matches[0].strip() if desc_matches else ''

    # Entity — from ContractingParty/PartyName (not ProcurementProject names)
    party_section = re.search(r'<cac:ContractingParty>.*?</cac:ContractingParty>', xml_text, re.DOTALL)
    entity = 'European Union Delegation'
    if party_section:
        org_name = re.search(r'<cbc:Name[^>]*>([^<]+)', party_section.group(0))
        if org_name:
            entity = org_name.group(1).strip()

    # Deadline
    deadline_match = re.search(r'<cbc:EndDate>([^<]+)', xml_text)
    deadline = ''
    if deadline_match:
        deadline = deadline_match.group(1).split('+')[0].split('T')[0]
        try:
            dl = datetime.strptime(deadline, '%Y-%m-%d')
            if dl < datetime.now() - timedelta(days=7):
                return None
        except ValueError:
            pass

    # Publication date
    pub_match = re.search(r'<efac:PublicationDate>([^<]+)', xml_text)
    if not pub_match:
        pub_match = re.search(r'<cbc:IssueDate>([^<]+)', xml_text)
    pub_date = pub_match.group(1).split('+')[0].split('T')[0] if pub_match else datetime.now().strftime('%Y-%m-%d')

    # Value
    value_match = re.search(r'<cbc:EstimatedOverallContractAmount[^>]*>([^<]+)', xml_text)
    value = float(value_match.group(1)) if value_match else None

    # Procedure type
    proc_match = re.search(r'<cbc:ProcedureCode[^>]*>([^<]+)', xml_text)
    procedure = proc_match.group(1) if proc_match else 'open'

    # Check for lots — each lot is a separate opportunity
    lot_names = []
    for lot_match in re.finditer(r'<cac:ProcurementProjectLot>.*?</cac:ProcurementProjectLot>', xml_text, re.DOTALL):
        lot_text = lot_match.group(0)
        lot_name_match = re.search(r'<cbc:Name\s+languageID="ENG"[^>]*>([^<]+)', lot_text)
        if not lot_name_match:
            lot_name_match = re.search(r'<cbc:Name[^>]*>([^<]+)', lot_text)
        if lot_name_match:
            lot_names.append(lot_name_match.group(1).strip())

    if lot_names and len(lot_names) > 1:
        description = f"{title}. Lots: " + "; ".join(lot_names[:10])

    if len(title) > 150:
        title = title[:147] + '...'

    ref = pub_num
    slug = slugify(f"eu-{title[:50]}-{ref}")
    category = categorize_tender(title + ' ' + description)
    ted_url = TED_HTML_URL.format(pub_num=pub_num)

    return {
        'title': title,
        'slug': slug,
        'reference_number': ref,
        'source': 'eu_ted',
        'source_url': ted_url,
        'procuring_entity': entity,
        'procuring_entity_slug': slugify(entity),
        'entity_type': 'international',
        'tender_type': notice_type,
        'procurement_method': procedure,
        'category': category,
        'subcategories': [],
        'sectors': [category],
        'description_short': f"{title[:100]} — EU-funded procurement",
        'description_long': description[:500] if description else f"European Union funded procurement: {title}. Published through Tenders Electronic Daily (TED).",
        'country': 'Malawi',
        'region': '',
        'city': '',
        'published_date': pub_date,
        'closing_date': deadline,
        'closing_time': '',
        'estimated_value': value,
        'currency': 'EUR',
        'funding_source': 'donor',
        'donor': 'European Union',
        'document_urls': [{'name': 'TED Notice', 'url': ted_url, 'type': 'link'}],
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


def fetch_ted_tenders():
    """Main fetch: search → fetch XMLs → parse → filter."""
    pub_numbers = search_ted_notices()
    if not pub_numbers:
        return []

    tenders = []
    checked = 0
    for pub_num in pub_numbers:
        xml_text = fetch_notice_xml(pub_num)
        checked += 1
        if not xml_text:
            continue
        tender = parse_notice_xml(xml_text, pub_num)
        if tender:
            tenders.append(tender)
            print(f"  MATCH: {pub_num} — {tender['title'][:80]}")

    print(f"  Checked {checked} XMLs, found {len(tenders)} Malawi open tenders")
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
    print("EU TED TENDER SCRAPER — Malawi")
    print("=" * 60)

    tenders = fetch_ted_tenders()
    print(f"\nFound {len(tenders)} open Malawi tenders")

    if tenders:
        saved, skipped = save_tenders(tenders)
        print(f"Saved: {saved} | Skipped (already exists): {skipped}")
    else:
        print("No open Malawi tenders found from TED.")

    print(f"Content dir: {CONTENT_DIR}")


if __name__ == '__main__':
    main()
