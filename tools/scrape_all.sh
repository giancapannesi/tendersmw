#!/bin/bash
# TendersMW — Run all scrapers, build, push, and submit to IndexNow
# Cron: 0 */6 * * * /srv/BusinessOps/tendersmw/tools/scrape_all.sh >> /tmp/tendersmw_scrape.log 2>&1

set -e
cd /srv/BusinessOps/tendersmw
source /srv/BusinessOps/.venv/bin/activate

echo "$(date) — TendersMW scrape starting"

# Snapshot existing slugs BEFORE scraping (so verifier skips them)
ls src/content/tenders/*.json 2>/dev/null | xargs -I{} basename {} .json > /tmp/tendersmw_existing_slugs.txt 2>/dev/null || true
BEFORE=$(wc -l < /tmp/tendersmw_existing_slugs.txt)

# Run scrapers
echo "Running PPDA scraper..."
python3 tools/ppda_scraper.py 2>&1 || echo "PPDA scraper failed"

echo "Running ESCOM scraper..."
python3 tools/escom_scraper.py 2>&1 || echo "ESCOM scraper failed"

echo "Running MRA scraper..."
python3 tools/mra_scraper.py 2>&1 || echo "MRA scraper failed"

echo "Running World Bank scraper..."
python3 tools/worldbank_scraper.py 2>&1 || echo "World Bank scraper failed"

# Count after scraping
AFTER=$(ls src/content/tenders/*.json 2>/dev/null | wc -l)
NEW=$((AFTER - BEFORE))

echo "Tenders: $BEFORE -> $AFTER ($NEW new)"

# AI VERIFICATION GATE — every new tender must be confirmed real
if [ "$NEW" -gt 0 ]; then
    echo "Running AI verification on $NEW new tenders..."
    python3 tools/verify_tender.py --batch src/content/tenders/ --existing-slugs-file /tmp/tendersmw_existing_slugs.txt 2>&1

    # Recount after verification (rejected tenders are deleted)
    AFTER=$(ls src/content/tenders/*.json 2>/dev/null | wc -l)
    NEW=$((AFTER - BEFORE))
    echo "After AI verification: $BEFORE -> $AFTER ($NEW verified new)"
fi

if [ "$NEW" -gt 0 ]; then
    echo "Building site..."
    npm run build 2>&1

    echo "Committing and pushing..."
    git add src/content/tenders/
    git commit -m "Auto-scrape: $NEW new tenders ($AFTER total)" || true
    git push origin main 2>&1

    # IndexNow
    echo "Submitting to IndexNow..."
    python3 -c "
import json, requests, os
urls = []
for root, dirs, files in os.walk('dist'):
    for f in files:
        if f == 'index.html':
            rel = os.path.relpath(root, 'dist')
            url = 'https://tendersmw.com/' if rel == '.' else f'https://tendersmw.com/{rel}/'
            urls.append(url)
payload = {'host': 'tendersmw.com', 'key': 'f2018aa106044007bf54b7cde9067a1e', 'urlList': urls}
r = requests.post('https://api.indexnow.org/indexnow', json=payload, headers={'Content-Type': 'application/json'})
print(f'IndexNow: {r.status_code} ({len(urls)} URLs)')
" 2>&1
else
    echo "No new tenders found, skipping build/push"
fi

echo "$(date) — TendersMW scrape complete"
