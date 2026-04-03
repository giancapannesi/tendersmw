#!/bin/bash
# TendersMW — Run all scrapers, build, push, and submit to IndexNow
# Cron: 0 */6 * * * /srv/BusinessOps/tendersmw/tools/scrape_all.sh >> /tmp/tendersmw_scrape.log 2>&1

set -e
cd /srv/BusinessOps/tendersmw
source /srv/BusinessOps/.venv/bin/activate

echo "$(date) — TendersMW scrape starting"

# Count before
BEFORE=$(ls src/content/tenders/*.json 2>/dev/null | wc -l)

# Run scrapers
echo "Running PPDA scraper..."
python3 tools/ppda_scraper.py 2>&1 || echo "PPDA scraper failed"

echo "Running ESCOM scraper..."
python3 tools/escom_scraper.py 2>&1 || echo "ESCOM scraper failed"

echo "Running MRA scraper..."
python3 tools/mra_scraper.py 2>&1 || echo "MRA scraper failed"

# Count after
AFTER=$(ls src/content/tenders/*.json 2>/dev/null | wc -l)
NEW=$((AFTER - BEFORE))

echo "Tenders: $BEFORE -> $AFTER ($NEW new)"

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
