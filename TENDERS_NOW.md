# TendersMW — LIVE STATE (RESUME-CURSOR)

> Read me first. Resume-cursor for TendersMW work.

---

## 10:30 CAT, 2026-05-07 — SITEMAP↔LIVE 404 AUDIT: CLEAN [SEO / sitemap]

**Finding.** Full audit of all 236 URLs in `dist/sitemap-0.xml` returned **0 404s**. Pipeline is healthy.

**Slug quality.** 28 slugs are >80 chars but they're auto-generated from real tender titles + procuring entity codes (e.g. `addendum-no-1-zcc-procurement-projects-2026-2027-zomba-city-council-zcc-procurement`). Intentional shape for that content type — not a bug. 0 non-ASCII, 0 trailing-dash, 0 %20.

**Daily refresh working.** Last commit `2026-05-06 11:00:08 UTC — Daily refresh: update tender statuses (236 pages)`. Cron pipeline that updates tender statuses end-to-end is functioning.

**Verification command.**
```bash
grep -oE '<loc>[^<]+</loc>' /srv/BusinessOps/tendersmw/dist/sitemap-0.xml | sed 's/<[^>]*>//g' \
  | while read url; do
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 -L "$url")
    [ "$code" != "200" ] && echo "$code $url"
  done
```

**Memory.** `memory/project_multisite_sitemap_audit_2026-05-07.md`.

---

## Stack notes (do not re-discover)
- Astro static site, Vercel-hosted.
- Sitemap generated at build time from `src/content/`. No DB.
- Live URL: `https://tendersmw.com/`.
- Indexing cron: `45 11 * * *` `gsc_indexing.py --site tendersmw --max-push 30`.
- Daily refresh updates tender statuses end-of-day; pipeline is the cleanest of the four sites today.
