#!/usr/bin/env python3
"""
AfDB (African Development Bank) Procurement Scraper — Fetches Malawi tenders.
Uses Playwright headless Chromium because the AfDB website returns 403 to plain HTTP clients.

Source: https://www.afdb.org/en/documents/project-related-procurement?tid=373
Country filter: tid=373 (Malawi)

Listing structure:
  - Date + Title + Link in SPAN.field-content elements
  - Pagination via ?page=N (0-indexed)

Detail page structure:
  - Description in og:description meta tag
  - Date in dcterms.date meta tag
  - PDF links in <a href="...pdf">
  - Body text with full description
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timedelta

# Base paths
CONTENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'content', 'tenders')
BASE_URL = 'https://www.afdb.org/en/documents/project-related-procurement'
MALAWI_TID = '373'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'

# Notice type prefixes and their mapping
NOTICE_TYPE_MAP = {
    'SPN': 'specific_procurement_notice',
    'GPN': 'general_procurement_notice',
    'EOI': 'request_for_expression_of_interest',
    'IFB': 'invitation_for_bids',
    'AMI': 'request_for_expression_of_interest',  # French: Avis de Manifestation d'Interet
    'AAO': 'invitation_for_bids',  # French: Appel d Offres
    'Contract Awards': 'contract_award',
}


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
    if any(w in title_lower for w in ['consultancy', 'consultant', 'advisory', 'evaluation', 'study', 'technical assistance', 'expression of interest']):
        return 'consulting'
    if any(w in title_lower for w in ['software', 'ict', 'computer', 'system', 'digital', 'network']):
        return 'technology'
    if any(w in title_lower for w in ['medical', 'health', 'pharmaceutical', 'hospital', 'nutrition']):
        return 'health'
    if any(w in title_lower for w in ['agriculture', 'farming', 'irrigation', 'fertilizer', 'food', 'seed', 'crop']):
        return 'agriculture'
    if any(w in title_lower for w in ['solar', 'energy', 'power', 'electricity', 'hydropower']):
        return 'energy'
    if any(w in title_lower for w in ['vehicle', 'transport', 'logistics', 'freight', 'corridor']):
        return 'transport'
    if any(w in title_lower for w in ['training', 'education', 'workshop', 'capacity building']):
        return 'education'
    if any(w in title_lower for w in ['water', 'wash', 'borehole', 'sewage', 'sanitation']):
        return 'water'
    if any(w in title_lower for w in ['environment', 'safeguard', 'climate', 'biodiversity']):
        return 'environment'
    return 'goods'


def parse_notice_type(title):
    """Extract the notice type prefix from the title (e.g. 'SPN', 'EOI', 'GPN')."""
    for prefix in NOTICE_TYPE_MAP:
        if title.startswith(prefix + ' ') or title.startswith(prefix + ' -'):
            return prefix, NOTICE_TYPE_MAP[prefix]
    return None, 'procurement_notice'


def extract_project_name(title):
    """Extract project name/code from the end of the title (typically after the last ' - ')."""
    parts = title.split(' - ')
    if len(parts) >= 2:
        return parts[-1].strip()
    return ''


def clean_title(title):
    """Remove the notice type prefix and country from the title for a cleaner display."""
    match = re.match(r'^(?:SPN|GPN|EOI|IFB|AMI|AAO|Contract Awards)\s*-\s*(?:Malawi|Multinational)\s*-\s*(.+)', title)
    if match:
        return match.group(1).strip()
    return title


def parse_afdb_date(date_str):
    """Parse AfDB date format like '08-May-2026' to 'YYYY-MM-DD'."""
    try:
        dt = datetime.strptime(date_str.strip(), '%d-%b-%Y')
        return dt.strftime('%Y-%m-%d')
    except (ValueError, AttributeError):
        return ''


def extract_deadline_from_text(text):
    """Try to extract a deadline/closing date from the body text."""
    if not text:
        return ''
    patterns = [
        r'(?:deadline|closing date|submission date|received by|not later than)[:\s]*(\d{1,2}[\s/-]\w+[\s/-]\d{4})',
        r'(\d{1,2}\s+\w+\s+\d{4})\s*(?:at|before|by)',
        r'(?:before|by|on)\s+(\d{1,2}\s+\w+\s+\d{4})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date_str = match.group(1).strip()
            for fmt in ['%d %B %Y', '%d-%B-%Y', '%d/%B/%Y', '%d %b %Y', '%d-%b-%Y']:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime('%Y-%m-%d')
                except ValueError:
                    continue
    return ''


async def fetch_listing_page(page, page_num=0):
    """Fetch a single page of the AfDB Malawi procurement listing."""
    url = f'{BASE_URL}?tid={MALAWI_TID}'
    if page_num > 0:
        url += f'&page={page_num}'

    try:
        resp = await page.goto(url, wait_until='domcontentloaded', timeout=45000)
        if resp.status != 200:
            print(f"  Page {page_num}: HTTP {resp.status}")
            return [], False

        await page.wait_for_timeout(5000)

        items = await page.evaluate('''() => {
            const results = [];
            const body = document.body.innerText;

            // Find all document links in the listing
            const links = document.querySelectorAll('span.field-content a');
            const dates = [];

            // Extract dates from text
            const datePattern = /(\\d{2}-[A-Z][a-z]{2}-\\d{4})/g;
            let match;
            while ((match = datePattern.exec(body)) !== null) {
                dates.push(match[1]);
            }

            let dateIdx = 0;
            for (const link of links) {
                const text = link.innerText.trim();
                const href = link.href;
                if (text.length > 20 && href.includes('/en/documents/') && !href.endsWith('/project-related-procurement')) {
                    results.push({
                        title: text,
                        url: href,
                        date: dateIdx < dates.length ? dates[dateIdx] : '',
                    });
                    dateIdx++;
                }
            }
            return results;
        }''')

        has_next = await page.evaluate('''() => {
            const nextLink = document.querySelector('li.pager-next a, a[title="Go to next page"]');
            return !!nextLink;
        }''')

        return items, has_next

    except Exception as e:
        print(f"  Error fetching page {page_num}: {e}")
        return [], False


async def fetch_detail_page(page, url):
    """Fetch detail info from an individual procurement notice page."""
    try:
        resp = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        if resp.status != 200:
            return {}

        await page.wait_for_timeout(4000)

        details = await page.evaluate('''() => {
            const result = {};

            const ogDesc = document.querySelector('meta[property="og:description"]');
            if (ogDesc) result.description = ogDesc.content;

            const dcDate = document.querySelector('meta[name="dcterms.date"]');
            if (dcDate) result.published_date = dcDate.content;

            const pdfLinks = [];
            document.querySelectorAll('a[href$=".pdf"]').forEach(a => {
                pdfLinks.push({name: a.innerText.trim() || 'Procurement Document', url: a.href, type: 'pdf'});
            });
            result.pdf_links = pdfLinks;

            // Body text
            const text = document.body.innerText;
            const startIdx = text.indexOf('You are here');
            const endIdx = text.indexOf('Related Sections');
            if (startIdx > -1 && endIdx > -1) {
                // Skip the breadcrumb line itself
                const content = text.substring(startIdx, endIdx);
                const lines = content.split('\\n').filter(l => l.trim().length > 0);
                // Skip "You are here" and "Home" lines, take the rest
                result.body_text = lines.slice(2).join('\\n').trim().substring(0, 2000);
            }

            return result;
        }''')

        return details

    except Exception as e:
        print(f"  Error fetching detail {url}: {e}")
        return {}


def build_tender(item, details):
    """Build a tender dict from listing item + detail page data."""
    title_raw = item['title']
    source_url = item['url']
    listing_date = parse_afdb_date(item.get('date', ''))

    prefix, tender_type = parse_notice_type(title_raw)

    # Skip contract awards
    if prefix == 'Contract Awards' or tender_type == 'contract_award':
        return None

    title = clean_title(title_raw)
    if not title or len(title) < 10:
        return None

    project_name = extract_project_name(title)

    description = details.get('description', '')
    body_text = details.get('body_text', '')

    # Extract deadline from body text
    deadline = extract_deadline_from_text(body_text) or extract_deadline_from_text(description)
    closing_date = deadline

    # Skip if deadline is more than 7 days in the past
    if closing_date:
        try:
            dl = datetime.strptime(closing_date, '%Y-%m-%d')
            if dl < datetime.now() - timedelta(days=7):
                return None
        except ValueError:
            pass

    # Published date
    published_raw = details.get('published_date', '')
    if published_raw:
        try:
            published_date = published_raw[:10]
            datetime.strptime(published_date, '%Y-%m-%d')
        except ValueError:
            published_date = listing_date or datetime.now().strftime('%Y-%m-%d')
    else:
        published_date = listing_date or datetime.now().strftime('%Y-%m-%d')

    # Reference from URL slug
    url_slug = source_url.rstrip('/').split('/')[-1]
    ref = url_slug[:60] if url_slug else ''

    slug = slugify(f"afdb-{title[:50]}-{ref[:30]}")

    category = categorize_tender(title)
    entity = 'African Development Bank / Government of Malawi'

    document_urls = details.get('pdf_links', [])
    if not document_urls:
        document_urls = [{'name': 'AfDB Notice', 'url': source_url, 'type': 'link'}]

    desc_short = description[:200] if description else f"AfDB procurement notice: {title}"
    desc_long = body_text[:1500] if body_text else description if description else f"African Development Bank funded procurement for {project_name or title}. Published through the AfDB procurement system."

    return {
        'title': title[:150],
        'slug': slug,
        'reference_number': ref,
        'source': 'afdb',
        'source_url': source_url,
        'procuring_entity': entity,
        'procuring_entity_slug': 'african-development-bank-government-of-malawi',
        'entity_type': 'international',
        'tender_type': tender_type,
        'procurement_method': 'open_competitive_bidding',
        'category': category,
        'subcategories': [],
        'sectors': [category],
        'description_short': desc_short,
        'description_long': desc_long,
        'country': 'Malawi',
        'region': '',
        'city': '',
        'published_date': published_date,
        'closing_date': closing_date,
        'closing_time': '',
        'estimated_value': None,
        'currency': 'USD',
        'funding_source': 'donor',
        'donor': 'African Development Bank',
        'document_urls': document_urls,
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


async def fetch_afdb_tenders(max_pages=3, fetch_details=True):
    """Main scraping function. Returns list of tender dicts."""
    from playwright.async_api import async_playwright

    tenders = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled'],
        )

        # Use one context for listing pages
        list_context = await browser.new_context(
            user_agent=USER_AGENT,
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Upgrade-Insecure-Requests': '1',
            },
        )
        list_page = await list_context.new_page()

        all_items = []
        for page_num in range(max_pages):
            print(f"  Fetching listing page {page_num + 1}...")
            items, has_next = await fetch_listing_page(list_page, page_num)
            print(f"    Found {len(items)} items")

            malawi_items = [i for i in items if 'malawi' in i.get('title', '').lower()]
            all_items.extend(malawi_items)

            if not has_next:
                break

        await list_context.close()
        print(f"\n  Total Malawi items from listings: {len(all_items)}")

        # Use fresh context for detail pages to avoid 403 after listing navigation
        for i, item in enumerate(all_items):
            details = {}
            if fetch_details:
                print(f"  [{i+1}/{len(all_items)}] Fetching details: {item['title'][:80]}...")
                if i > 0:
                    await asyncio.sleep(1)
                detail_context = await browser.new_context(
                    user_agent=USER_AGENT,
                    extra_http_headers={
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                    },
                )
                detail_page = await detail_context.new_page()
                details = await fetch_detail_page(detail_page, item['url'])
                await detail_context.close()
                if details.get('description'):
                    print(f"    OK: {details['description'][:80]}...")

            tender = build_tender(item, details)
            if tender:
                tenders.append(tender)

        await browser.close()

    return tenders


def save_tenders(tenders):
    """Save tenders to JSON files. Skip if file already exists (same slug)."""
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
    print("AfDB TENDER SCRAPER — Malawi")
    print("=" * 60)

    tenders = asyncio.run(fetch_afdb_tenders())
    print(f"\nFound {len(tenders)} open Malawi tenders")

    if tenders:
        saved, skipped = save_tenders(tenders)
        print(f"Saved: {saved} | Skipped (already exists): {skipped}")
        for t in tenders:
            deadline_info = f" | Deadline: {t['closing_date']}" if t['closing_date'] else " | No deadline found"
            print(f"  - {t['title'][:80]}{deadline_info}")
    else:
        print("No open Malawi tenders found from AfDB.")

    print(f"Content dir: {CONTENT_DIR}")


if __name__ == '__main__':
    main()
