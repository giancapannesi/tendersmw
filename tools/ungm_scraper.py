#!/usr/bin/env python3
"""
UNGM + UNDP Procurement Scraper — Fetches Malawi tenders from UN sources.

Sources:
1. UNGM (United Nations Global Marketplace) — ungm.org/Public/Notice
   Fully JS-rendered, requires Playwright headless browser.
   Structure: country filter -> search -> div[class*="notice"] results with
   div.resultTitle, div.deadline, div.resultAgency, a[href*="/Public/Notice/<id>"]
2. UNDP Procurement Notices — procurement-notices.undp.org
   JS-rendered text blocks with TITLE/REF NO/UNDP OFFICE/COUNTRY/PROCESS/DEADLINE/POSTED labels.

ABSOLUTE RULE: NEVER generate fake/sample/placeholder data.
If no tenders are found, save nothing and exit cleanly.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta
from html import unescape

CONTENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'content', 'tenders')


def slugify(text):
    """Create URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:80].rstrip('-')


def clean_html(text):
    """Strip HTML tags and normalize whitespace."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def categorize_tender(title):
    """Categorize tender based on title keywords."""
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


def parse_deadline(date_str):
    """Try multiple date formats to parse a deadline string. Returns (date_str_iso, datetime_obj) or (None, None)."""
    if not date_str:
        return None, None
    date_str = date_str.strip()
    formats = [
        '%Y-%m-%d',
        '%d-%b-%Y',
        '%d %b %Y',
        '%d/%m/%Y',
        '%m/%d/%Y',
        '%B %d, %Y',
        '%d %B %Y',
        '%d-%m-%Y',
        '%Y/%m/%d',
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d'), dt
        except ValueError:
            continue
    return None, None


def is_deadline_valid(deadline_iso):
    """Return True if deadline is not more than 7 days in the past."""
    if not deadline_iso:
        return True  # No deadline = keep it (might still be open)
    try:
        dl = datetime.strptime(deadline_iso, '%Y-%m-%d')
        return dl >= datetime.now() - timedelta(days=7)
    except ValueError:
        return True


def build_tender_dict(title, ref, entity, deadline_iso, description, source_url, source_name='ungm'):
    """Build a tender dict matching the worldbank_scraper.py format."""
    slug = slugify(f"{source_name}-{title[:50]}-{ref}")
    category = categorize_tender(title + ' ' + description)
    entity_slug = slugify(entity) if entity else source_name

    # Determine tender type from title + description
    combined_lower = (title + ' ' + description).lower()
    if 'expression of interest' in combined_lower or 'eoi' in combined_lower:
        tender_type = 'expression_of_interest'
    elif 'request for proposal' in combined_lower or 'rfp' in combined_lower:
        tender_type = 'request_for_proposal'
    elif 'request for quotation' in combined_lower or 'rfq' in combined_lower:
        tender_type = 'request_for_quotation'
    elif 'invitation for bid' in combined_lower or 'invitation to bid' in combined_lower or 'ifb' in combined_lower or 'itb' in combined_lower:
        tender_type = 'invitation_for_bids'
    elif 'individual c' in combined_lower or ' ic ' in combined_lower:
        tender_type = 'individual_consultant'
    else:
        tender_type = 'open_tender'

    if len(title) > 150:
        title = title[:147] + '...'

    return {
        'title': title,
        'slug': slug,
        'reference_number': ref or '',
        'source': source_name,
        'source_url': source_url,
        'procuring_entity': entity or f'United Nations ({source_name.upper()})',
        'procuring_entity_slug': entity_slug,
        'entity_type': 'international',
        'tender_type': tender_type,
        'procurement_method': 'open_competitive_bidding',
        'category': category,
        'subcategories': [],
        'sectors': [category],
        'description_short': description[:200] if description else title,
        'description_long': description or title,
        'country': 'Malawi',
        'region': '',
        'city': '',
        'published_date': datetime.now().strftime('%Y-%m-%d'),
        'closing_date': deadline_iso or '',
        'closing_time': '',
        'estimated_value': None,
        'currency': 'USD',
        'funding_source': 'donor',
        'donor': entity or 'United Nations',
        'document_urls': [{'name': f'{source_name.upper()} Notice', 'url': source_url, 'type': 'link'}],
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


# ---------------------------------------------------------------------------
# UNGM Scraper
# ---------------------------------------------------------------------------

def scrape_ungm_page(page):
    """
    Extract tenders from the current UNGM search results page.
    UNGM structure: div[class*="notice"] contains each result, with child divs:
      - div.resultTitle = title text
      - div[class*="deadline"] = deadline string
      - div.resultAgency = UN agency abbreviation
    Links: a[href*="/Public/Notice/"] with numeric IDs.
    """
    tenders = []
    notice_divs = page.query_selector_all('div[class*="notice"]')
    # Only keep divs that contain a notice link (skip filter tags, empty ones)
    result_divs = [d for d in notice_divs if d.query_selector('a[href*="/Public/Notice/"]')]

    for div in result_divs:
        try:
            # Title
            title_el = div.query_selector('div[class*="resultTitle"]')
            title = title_el.inner_text().strip() if title_el else ''

            # Link + notice ID
            link_el = div.query_selector('a[href*="/Public/Notice/"]')
            href = link_el.get_attribute('href') if link_el else ''
            if href and href.startswith('/'):
                href = f"https://www.ungm.org{href}"
            ref_match = re.search(r'/Public/Notice/(\d+)', href or '')
            notice_id = ref_match.group(1) if ref_match else ''

            # Reference text from the full block (e.g. "rfx_6609_HQ", "UNFPA/EECARO/RFQ/2026/004", "ITB/2026/62096")
            full_text = div.inner_text().strip()
            ref_text_match = re.search(r'(rfx[_\-]\w+|[A-Z]{2,}/[A-Z0-9]+/[A-Z0-9/]+|ITB/\d+/\d+)', full_text)
            ref = ref_text_match.group(0) if ref_text_match else notice_id

            # Deadline
            deadline_el = div.query_selector('div[class*="deadline"]')
            deadline_text = deadline_el.inner_text().strip() if deadline_el else ''
            deadline_iso = None
            if deadline_text:
                date_match = re.search(r'(\d{1,2}-\w{3}-\d{4})', deadline_text)
                if date_match:
                    deadline_iso, _ = parse_deadline(date_match.group(1))

            # Agency
            agency_el = div.query_selector('div[class*="resultAgency"]')
            agency = agency_el.inner_text().strip() if agency_el else 'United Nations'

            if not title or not href:
                continue
            if not is_deadline_valid(deadline_iso):
                continue

            description = f"{title}. Published by {agency} via UNGM."
            if ref and ref != notice_id:
                description += f" Reference: {ref}."

            tender = build_tender_dict(
                title=clean_html(title),
                ref=ref or notice_id,
                entity=agency,
                deadline_iso=deadline_iso,
                description=description,
                source_url=href,
                source_name='ungm',
            )
            tenders.append(tender)
        except Exception as e:
            print(f"    Error parsing UNGM notice: {e}")
    return tenders


def scrape_ungm(page):
    """
    Scrape UNGM for Malawi tenders.
    1. Load search page
    2. Select Malawi in country filter
    3. Click Search
    4. Paginate through results (15 per page, cap at 5 pages)
    """
    tenders = []
    print("\n--- UNGM Scraper ---")
    print("Loading https://www.ungm.org/Public/Notice ...")

    try:
        page.goto('https://www.ungm.org/Public/Notice', wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(3000)

        # Step 1: Country filter
        country_input = None
        for sel in ['input[placeholder*="country" i]', 'input[placeholder*="Country" i]']:
            el = page.query_selector(sel)
            if el and el.is_visible():
                country_input = el
                break

        if country_input:
            country_input.click()
            country_input.fill('Malawi')
            page.wait_for_timeout(2000)
            for opt_sel in ['li:has-text("Malawi")', 'option:has-text("Malawi")']:
                opt = page.query_selector(opt_sel)
                if opt and opt.is_visible():
                    opt.click()
                    print("  Selected Malawi in country filter")
                    break
            page.wait_for_timeout(2000)
        else:
            print("  WARNING: Could not find country filter")

        # Step 2: Click Search
        for b in page.query_selector_all('button'):
            if 'search' in b.inner_text().strip().lower():
                b.click()
                print("  Clicked Search")
                break
        page.wait_for_timeout(8000)

        # Step 3: Check result count
        results_el = page.query_selector('div.resultsCount')
        results_text = results_el.inner_text().strip() if results_el else ''
        print(f"  Results: {results_text}")
        total_match = re.search(r'of\s+(\d+)', results_text)
        total_results = int(total_match.group(1)) if total_match else 0

        # Step 4: Extract page 1
        page_tenders = scrape_ungm_page(page)
        tenders.extend(page_tenders)
        print(f"  Page 1: {len(page_tenders)} tenders")

        # Step 5: Paginate (cap at 5 pages = 75 results)
        # The filter overlay intercepts normal clicks, so we scroll down
        # past it and use force=True or JS click as fallback.
        if total_results > 15:
            max_pages = min((total_results + 14) // 15, 5)
            for page_num in range(2, max_pages + 1):
                try:
                    # Scroll down to get past the filter overlay
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    page.wait_for_timeout(1000)

                    next_btn = page.query_selector(f'a:has-text("{page_num}")')
                    if not next_btn:
                        next_btn = page.query_selector('a[aria-label="Next"], a:has-text(">")')
                    if next_btn:
                        try:
                            next_btn.click(force=True, timeout=10000)
                        except Exception:
                            # JS click fallback
                            next_btn.dispatch_event('click')
                        page.wait_for_timeout(5000)
                        pt = scrape_ungm_page(page)
                        tenders.extend(pt)
                        print(f"  Page {page_num}: {len(pt)} tenders")
                    else:
                        break
                except Exception as e:
                    print(f"  Pagination error page {page_num}: {e}")
                    break

    except Exception as e:
        print(f"  UNGM scraper error: {e}")

    print(f"  UNGM total: {len(tenders)} Malawi tenders")
    return tenders


# ---------------------------------------------------------------------------
# UNDP Scraper
# ---------------------------------------------------------------------------

def scrape_undp(page):
    """
    Scrape UNDP Procurement Notices for Malawi tenders.
    The page renders all notices as text blocks with labels:
      TITLE / REF NO / UNDP OFFICE/COUNTRY / PROCESS / DEADLINE / POSTED
    We split on "TITLE" to get blocks, filter for MALAWI in UNDP OFFICE/COUNTRY.
    """
    tenders = []
    print("\n--- UNDP Procurement Scraper ---")
    url = 'https://procurement-notices.undp.org/search.cfm'
    print(f"Loading {url} ...")

    try:
        page.goto(url, wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(5000)

        body_text = page.inner_text('body')
        print(f"  Page text length: {len(body_text)} chars")

        # Split into blocks by TITLE label
        blocks = re.split(r'\nTITLE\n', body_text)
        total_blocks = len(blocks) - 1  # First is header
        print(f"  Total notice blocks: {total_blocks}")

        # Filter for Malawi
        malawi_blocks = [b for b in blocks[1:] if 'MALAWI' in b.upper()]
        print(f"  Malawi blocks: {len(malawi_blocks)}")

        for block in malawi_blocks:
            try:
                lines = block.strip().split('\n')
                if not lines:
                    continue

                title = lines[0].strip()
                if not title or len(title) < 5:
                    continue

                # Parse structured fields
                ref = ''
                office_country = ''
                process = ''
                deadline_str = ''

                i = 1
                while i < len(lines):
                    line = lines[i].strip()
                    if line == 'REF NO' and i + 1 < len(lines):
                        ref = lines[i + 1].strip()
                        i += 2
                    elif line == 'UNDP OFFICE/COUNTRY' and i + 1 < len(lines):
                        office_country = lines[i + 1].strip()
                        i += 2
                    elif line == 'PROCESS' and i + 1 < len(lines):
                        process = lines[i + 1].strip()
                        i += 2
                    elif line == 'DEADLINE' and i + 1 < len(lines):
                        deadline_str = lines[i + 1].strip()
                        # Skip time line if present
                        if i + 2 < len(lines) and ('AM' in lines[i + 2] or 'PM' in lines[i + 2]):
                            i += 3
                        else:
                            i += 2
                    elif line == 'POSTED' and i + 1 < len(lines):
                        i += 2
                    else:
                        i += 1

                # Parse deadline (format: "25-May-26")
                deadline_iso = None
                if deadline_str:
                    date_match = re.search(r'(\d{1,2}-\w{3}-\d{2,4})', deadline_str)
                    if date_match:
                        raw = date_match.group(1)
                        parts = raw.split('-')
                        if len(parts) == 3 and len(parts[2]) == 2:
                            parts[2] = '20' + parts[2]
                            raw = '-'.join(parts)
                        deadline_iso, _ = parse_deadline(raw)

                if not is_deadline_valid(deadline_iso):
                    continue

                # Entity from office_country (e.g. "UNDP-MWI/MALAWI", "WHO Country Office/MALAWI")
                entity = 'UNDP'
                for un_org in ['UNICEF', 'WFP', 'WHO', 'UNFPA', 'UNOPS', 'FAO', 'UNESCO', 'UNHCR', 'IOM', 'UN Women', 'UNDP']:
                    if un_org in office_country.upper():
                        entity = un_org
                        break

                # Build source URL — numeric refs link directly to the notice
                if ref and ref.isdigit():
                    source_url = f"https://procurement-notices.undp.org/view.cfm?notice_id={ref}"
                else:
                    # For UNDP-XXX-NNNNN style refs, search by ref
                    source_url = f"https://procurement-notices.undp.org/search.cfm?ref={ref}" if ref else url

                description = f"{title}. {process}. {office_country}."

                tender = build_tender_dict(
                    title=clean_html(title),
                    ref=ref,
                    entity=entity,
                    deadline_iso=deadline_iso,
                    description=description,
                    source_url=source_url,
                    source_name='ungm',
                )
                tenders.append(tender)
            except Exception as e:
                print(f"  Error parsing UNDP block: {e}")

    except Exception as e:
        print(f"  UNDP scraper error: {e}")

    print(f"  UNDP: found {len(tenders)} Malawi tenders")
    return tenders


# ---------------------------------------------------------------------------
# Save + Main
# ---------------------------------------------------------------------------

def save_tenders(tenders):
    """Save tenders to JSON files. Skip if slug already exists."""
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
    print("UNGM + UNDP TENDER SCRAPER — Malawi")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    all_tenders = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 800},
        )
        page = context.new_page()

        # Source 1: UNGM
        try:
            ungm_tenders = scrape_ungm(page)
            all_tenders.extend(ungm_tenders)
        except Exception as e:
            print(f"UNGM scraping failed: {e}")

        # Source 2: UNDP Procurement
        try:
            undp_tenders = scrape_undp(page)
            all_tenders.extend(undp_tenders)
        except Exception as e:
            print(f"UNDP scraping failed: {e}")

        browser.close()

    # Deduplicate by slug
    seen_slugs = set()
    unique_tenders = []
    for t in all_tenders:
        if t['slug'] not in seen_slugs:
            seen_slugs.add(t['slug'])
            unique_tenders.append(t)

    print(f"\nTotal unique tenders found: {len(unique_tenders)}")

    if unique_tenders:
        saved, skipped = save_tenders(unique_tenders)
        print(f"Saved: {saved} | Skipped (already exists): {skipped}")
        for t in unique_tenders:
            print(f"  - {t['title'][:80]} | Deadline: {t['closing_date'] or 'N/A'} | Ref: {t['reference_number']}")
    else:
        print("No open Malawi tenders found from UNGM/UNDP sources.")
        print("This is normal — tenders are posted periodically. Run again later.")

    print(f"Content dir: {CONTENT_DIR}")


if __name__ == '__main__':
    main()
