# TendersMW 6-Month Strategy (Apr–Sep 2026)

**Date:** 2026-04-03
**Author:** Claude (Business Partner, Cosmic Phoenix LLC)
**Status:** DRAFT — Requires founder review

---

## Executive Summary

TendersMW is live with 149 tenders from 3 sources (PPDA, ESCOM, MRA), 205 pages, and automated scraping every 6h. The site is indexed in Google with 442 impressions in 7 days.

**The goal:** $1,500/month revenue by Month 6 from a combination of subscriptions, per-bid fees, and WhatsApp bot payments.

**The honest assessment:** This is achievable but requires disciplined execution. The Malawi market is small (4M internet users), payments infrastructure is limited, and adoption will be slow. Conservative estimate: $625–950/month by Month 6 if everything goes right. $1,500/month is the optimistic ceiling requiring strong word-of-mouth.

**What we sell:**
1. **SmartMatch Alerts** — AI-matched tender notifications ($10/month or $100/year)
2. **AI Bid Writer** — First-draft tender documents ($15–25/bid)
3. **WhatsApp OCR Bot** — Photo of newspaper ad → structured tender data ($5/month or $0.50/scan)
4. **Premium Analytics** — Entity intelligence, win rates, price benchmarks ($25/month)

**How we get paid:**
- **International (USD):** Stripe via Cosmic Phoenix LLC (US bank account already exists at Mercury)
- **Local (MWK):** PayChangu — Malawi's leading payment gateway (Airtel Money + TNM Mpamba + bank cards, ~3% fee)
- **Fallback:** DPO Pay (Pan-African, Lilongwe office) or Pesapal (regional)

---

## Current State (Apr 3, 2026)

| Metric | Value |
|--------|-------|
| Pages | 205 |
| Tenders | 149 (42 PPDA + 8 ESCOM + 99 MRA) |
| Sources | 3 active scrapers |
| GSC Impressions (7d) | 442 |
| GSC Clicks (7d) | 6 |
| Users | 0 (no accounts yet) |
| Revenue | $0 |
| Monthly cost | ~$0 (Vercel free tier, VPS shared) |
| Competitor | malawitenders.com ($249–449/yr, no AI, Indian-operated) |

---

## Month 1 (April 2026): Foundation + Data Moat

### 1.1 Expand Data Sources
**Goal:** 500+ tenders from 6+ sources

| Source | Method | Expected Tenders | Effort |
|--------|--------|-----------------|--------|
| MANEPS | Next.js JSON API | 50–200 | 2 days |
| World Bank | JS SPA scraping | 20–50 | 2 days |
| EU TED | REST API v3 (POST, XML) | 5–15 high-value | 1 day |
| Water Boards (LWB, BWB, CRWB) | Static HTML | 10–20 | 1 day |
| UNICEF/UNDP | Portal scraping | 10–30 | 1 day |

**Self-hosted scraping stack (replaces Apify — saves $64/month):**
- `curl_cffi` for 70% of sites (TLS fingerprint spoofing, no browser needed)
- `Playwright` for JS-heavy sites (MANEPS, World Bank) as fallback
- SQLite queue + cron architecture (matching existing VPS patterns)
- DataImpulse residential proxy ($1/GB) — only for AfDB/UNGM that block cloud IPs
- **Cost: $3–15/month** vs $64/month Apify

All Malawi government sites (PPDA, ESCOM, MRA, Water Boards) have **zero anti-bot protection**. No proxies needed.

### 1.2 Build Scraper Infrastructure
**Goal:** Reusable scraping framework for all future sources

```
/srv/BusinessOps/tendersmw/tools/
├── scrapers/
│   ├── base_scraper.py      # Abstract base: fetch, parse, save, dedup
│   ├── ppda_scraper.py      # Existing
│   ├── escom_scraper.py     # Existing
│   ├── mra_scraper.py       # Existing
│   ├── maneps_scraper.py    # NEW
│   ├── worldbank_scraper.py # NEW
│   ├── eu_ted_scraper.py    # NEW (XML enrichment)
│   └── waterboard_scraper.py # NEW
├── scrape_all.sh            # Existing
└── scraper_queue.db         # SQLite: URLs, last_scraped, status
```

### 1.3 Payment Integration
**Goal:** Accept both USD (international) and MWK (local mobile money)

**Stripe (USD — international customers, NGOs, diaspora):**
- Already have Cosmic Phoenix LLC EIN (35-2791755) + Mercury bank account
- Stripe Checkout for subscription plans
- Webhook endpoint on Vercel serverless function
- Estimated setup: 1–2 days

**PayChangu (MWK — local Malawian businesses):**
- Leading Malawi payment gateway: 4,000+ merchants, 5 years operating
- Supports: Airtel Money, TNM Mpamba, National Bank, FDH Bank, NBS Bank
- Fees: ~3% per transaction (competitive for Malawi)
- API: REST with webhooks, well-documented
- Registration: online at paychangu.com, needs Malawi business registration
- **GIAN ACTION:** Register Cosmic Phoenix LLC (or local entity) on PayChangu
- Estimated setup: 2–3 days after registration

**Payment architecture:**
```
User clicks "Subscribe" →
  If international → Stripe Checkout (USD)
  If Malawian → PayChangu (MWK via Airtel/Mpamba)
  → Webhook confirms payment → Enable premium features
  → Supabase `subscriptions` table tracks status
```

**Mobile money is critical.** 95% of Malawian internet users access via mobile. Mobile money penetration is higher than bank card penetration. If we only support Stripe, we lose 80%+ of the local market.

### 1.4 SEO & Content
- Add GA4 tracking (GIAN needs to create property)
- Publish 2 more guides: "Documents Checklist for Tender Submission" + "Understanding Procurement Methods"
- Region/district pages (28 districts = 28 new pages)
- Tender document checklist tool (interactive)
- Target: 400+ pages by end of month

### Month 1 Costs
| Item | Cost |
|------|------|
| DataImpulse proxy (if needed) | $1–5 |
| Stripe | $0 (pay-as-you-go) |
| PayChangu registration | $0 (or small local fee) |
| Claude API (testing) | $2–5 |
| **Total** | **$3–10** |

### Month 1 Revenue: $0
Building the foundation. No revenue expected.

---

## Month 2 (May 2026): SmartMatch + WhatsApp Bot (First Revenue)

### 2.1 SmartMatch AI Alerts
**What:** Business creates a profile (sectors, categories, regions, certifications, past contracts). AI matches new tenders against profile and sends alerts via email + WhatsApp.

**How it works:**
1. User fills a simple form: company name, sectors (checkboxes), max contract value, region preferences
2. Every scraper run (6h), new tenders are compared against all profiles
3. Stage 1: Fast filter (category + region + value range) — eliminates 90%
4. Stage 2: Claude API semantic scoring of remaining candidates — $0.0013/match
5. Matches above threshold → WhatsApp message + email with tender details + direct link

**Pricing:**
- Free tier: 3 matches/week, email only, 24h delay
- Basic ($10/month or $100/year): Unlimited matches, WhatsApp + email, real-time
- Pro ($25/month or $250/year): + priority alerts, sector analysis, win rate data

**Why $10/month works in Malawi:** Companies currently spend $249–449/year on malawitenders.com for basic listings with zero AI. $10/month ($120/year) is 50% cheaper with 10x better matching.

**Technical build:**
- Supabase: `profiles`, `matches`, `subscriptions` tables
- WhatsApp Business API via 360dialog or Twilio (~$0.005/message)
- Claude API for semantic matching (~$0.0013/match)
- Cron: runs after each scraper cycle

### 2.2 WhatsApp OCR Bot — THE COMPETITIVE MOAT
**What:** User sends a photo of a newspaper tender ad → bot extracts all structured data in 30 seconds → tender appears on site.

**Why this is the moat:** 30–40% of Malawi government tenders are published ONLY in newspapers (The Daily Times, The Nation, Malawi News). No competitor digitizes these. PPDA only posts tenders above MK50M online. Everything below that threshold is newspaper-only.

**How it works:**
1. User sends photo of newspaper tender to WhatsApp number
2. Claude multimodal API reads the image — $0.003/photo
3. Extracts: title, procuring entity, closing date, reference number, requirements, contact info
4. Returns structured summary to user + publishes to site (after basic QA)
5. User gets "credit" for contribution → incentive loop

**Pricing:**
- Free: 3 scans/month (community contribution model)
- Premium ($5/month): Unlimited scans, instant alerts when newspaper tenders match profile
- Per-scan: $0.50 via mobile money (for casual users)

**Cost per scan: $0.003** (Claude multimodal). Even at $0.50/scan, that's 99.4% gross margin.

### 2.3 User Accounts + Dashboard
- Supabase auth (email + phone number)
- User dashboard: saved tenders, alerts, profile, subscription status
- Admin dashboard: user metrics, revenue, scraper health

### Month 2 Costs
| Item | Cost |
|------|------|
| Supabase (free tier) | $0 |
| Claude API (matching + OCR) | $10–30 |
| WhatsApp Business API | $10–20 |
| DataImpulse proxy | $1–5 |
| **Total** | **$21–55** |

### Month 2 Revenue Target: $50–200
- 5–20 SmartMatch subscribers × $10 = $50–200
- WhatsApp OCR: mostly free tier (building community)
- **Conservative:** $50. **Optimistic:** $200.

---

## Month 3 (June 2026): AI Bid Writer + Scale

### 3.1 AI Bid Writer
**What:** User uploads a tender document (PDF) + provides company profile → AI generates a first-draft bid document (technical proposal, methodology, compliance matrix, pricing structure).

**How it works:**
1. User uploads tender PDF + selects their company profile
2. Claude API extracts tender requirements from PDF
3. Claude generates draft bid: executive summary, technical approach, methodology, team composition, compliance matrix, pricing template
4. Output: downloadable DOCX (using existing `create_docx.py` tool)
5. User edits, refines, submits

**What it does NOT do:** It doesn't write the final bid. It creates a 60–70% complete draft that the bidder then customizes. This is still a massive time-saver for companies that currently start from blank pages.

**Pricing:**
- $15/bid for basic bids (supplies, simple services)
- $25/bid for complex bids (construction, consulting, multi-lot)
- $50–100/month unlimited plan for frequent bidders
- **API cost: $0.10–0.30/bid** (Claude processing full PDF + generating 5–10 page document)

**Why companies will pay:** Hiring a bid writer in Malawi costs $200–500 per bid. $15–25 is a no-brainer, even for a first draft.

### 3.2 Newspaper Tender Network
- Recruit 5–10 contributors in major cities (Lilongwe, Blantyre, Mzuzu, Zomba)
- Each sends 2–5 newspaper photos/day via WhatsApp
- Payment: $0.50/verified tender photo (via mobile money)
- Cost: $2.50–25/day = $75–750/month
- **Revenue potential:** These tenders are invisible to competitors. Exclusive data = premium value.

### 3.3 MANEPS Integration
- MANEPS goes mandatory April 2026 but adoption is at 16% (32/200 PDEs)
- As more entities onboard, tender volume will increase
- Our scraper captures these automatically
- **Positioning:** "See MANEPS tenders + newspaper tenders + donor tenders all in one place"

### Month 3 Costs
| Item | Cost |
|------|------|
| Claude API (matching + OCR + bid writing) | $30–80 |
| WhatsApp Business API | $15–30 |
| Newspaper contributor payments | $75–300 |
| DataImpulse proxy | $1–5 |
| **Total** | **$121–415** |

### Month 3 Revenue Target: $300–800
- 20–40 SmartMatch subscribers × $10 = $200–400
- 5–15 bid writer uses × $15–25 = $75–375
- WhatsApp OCR subscriptions: $25–50
- **Conservative:** $300. **Optimistic:** $800.

---

## Month 4 (July 2026): Analytics + Entity Intelligence

### 4.1 Procurement Analytics Dashboard
**What:** Data-driven insights that no competitor offers.

- **Entity profiles:** Award history, average contract values, payment timelines, reliability scores
- **Sector trends:** Which sectors are growing/shrinking, seasonal patterns
- **Price benchmarks:** What similar tenders have been awarded for historically
- **Win rate analysis:** How competitive is a specific tender category

**Data sources:**
- Our scraped tender data (growing daily)
- PPDA annual reports (public, we have the PDFs)
- Award notices (when available)
- User-submitted award results (community contribution)

**Pricing:**
- Basic analytics included in Pro plan ($25/month)
- Entity intelligence reports: $10/report (one-off)
- Sector reports: $25/report (quarterly)

### 4.2 WhatsApp Channel (Free Marketing)
- WhatsApp Channel for daily tender updates (free to create, free to follow)
- Post: 3–5 new tenders daily + weekly procurement news
- Builds audience → converts to paid SmartMatch subscribers
- **GIAN ACTION:** Create WhatsApp Channel

### 4.3 Community Building
- "Procurement Corner" weekly newsletter (free, email)
- LinkedIn presence targeting Malawi procurement professionals
- Partnerships with: MCCCI (Chamber of Commerce), SMEDI (SME Development Institute)

### Month 4 Costs
| Item | Cost |
|------|------|
| Claude API | $40–100 |
| WhatsApp Business API | $20–40 |
| Newspaper contributors | $100–400 |
| DataImpulse proxy | $2–10 |
| **Total** | **$162–550** |

### Month 4 Revenue Target: $500–1,200
- 40–60 SmartMatch subscribers × $10 = $400–600
- 10–25 bid writer uses × $15–25 = $150–625
- WhatsApp OCR: $50–100
- Analytics reports: $50–100
- **Conservative:** $500. **Optimistic:** $1,200.

---

## Month 5 (August 2026): Automation + Partnerships

### 5.1 Autonomous Agent Bundle
**What:** AI agent that monitors tenders 24/7 on behalf of a company.

- Auto-applies initial compliance checks ("Are we eligible?")
- Pre-fills standard form sections (company details, past contracts, financial statements)
- Alerts when a competitor wins a tender you bid on
- Tracks procurement calendar (budget cycles, quarterly tender releases)

**Pricing:** $50–100/month (premium tier)

### 5.2 B2B Partnerships
- **NGOs and donor agencies:** Offer bulk subscriptions for implementing partners
- **Accounting/law firms:** White-label tender alerts for their clients
- **Banks:** Partner with FDH/NBS for SME lending tied to tender wins
- **MCCCI/SMEDI:** Offer discounted group rates for member organizations

### 5.3 Fintech Grant Applications
**Submit to (all have Malawi-specific programs):**
- UNCDF Malawi Fintech Challenge — up to $100K (50% co-fund)
- mHub Growth Accelerator — $10K–$40K (KfW-funded)
- UNDP Accelerator Lab Malawi — innovation grants
- Mastercard Foundation Young Africa Works — digital skills + enterprise

**These grants fund exactly what we're building:** digital procurement tools for SMEs in Sub-Saharan Africa. The pitch writes itself.

### Month 5 Costs
| Item | Cost |
|------|------|
| Claude API | $50–120 |
| WhatsApp Business API | $25–50 |
| Newspaper contributors | $150–500 |
| DataImpulse proxy | $5–15 |
| Grant application costs | $0 |
| **Total** | **$230–685** |

### Month 5 Revenue Target: $800–1,800
- 60–100 SmartMatch subscribers × $10 = $600–1,000
- 15–30 bid writer uses × $15–25 = $225–750
- WhatsApp OCR + Analytics: $100–200
- Agent bundle: $50–200 (early adopters)
- **Conservative:** $800. **Optimistic:** $1,800.

---

## Month 6 (September 2026): Scale + Optimize

### 6.1 Optimization
- A/B test pricing (is $15/bid too low? Test $20–30)
- Churn analysis (why do subscribers cancel?)
- Conversion funnel optimization (free → paid)
- Content SEO for long-tail procurement queries

### 6.2 Regional Expansion Prep
- Research Tanzania, Zambia, Mozambique procurement systems
- Same playbook: scrape → aggregate → AI-match → sell
- Each country = separate domain + shared infrastructure
- Decision point: expand or deepen Malawi?

### 6.3 Revenue Optimization
- Annual plan discount (2 months free → improves cash flow)
- Referral program (1 free month for each referral)
- Enterprise plans for large construction/consulting firms ($100–200/month)

### Month 6 Costs
| Item | Cost |
|------|------|
| Claude API | $60–150 |
| WhatsApp Business API | $30–60 |
| Newspaper contributors | $200–600 |
| DataImpulse proxy | $5–15 |
| Marketing (WhatsApp ads, LinkedIn) | $50–100 |
| **Total** | **$345–925** |

### Month 6 Revenue Target: $625–1,500
- 80–120 SmartMatch subscribers × $10 = $800–1,200
- 20–40 bid writer uses × $15–25 = $300–1,000
- WhatsApp OCR + Analytics: $150–300
- Agent bundle: $100–400
- **Gross revenue: $1,350–2,900**
- **Minus costs: $345–925**
- **Net: $625–1,975**

---

## 6-Month Revenue Projection (Conservative)

| Month | Subscribers | Bid Sales | Other | Gross | Costs | Net |
|-------|------------|-----------|-------|-------|-------|-----|
| 1 (Apr) | 0 | 0 | 0 | $0 | $10 | -$10 |
| 2 (May) | $100 | $0 | $25 | $125 | $55 | $70 |
| 3 (Jun) | $250 | $150 | $50 | $450 | $300 | $150 |
| 4 (Jul) | $450 | $250 | $75 | $775 | $450 | $325 |
| 5 (Aug) | $700 | $375 | $125 | $1,200 | $600 | $600 |
| 6 (Sep) | $900 | $500 | $200 | $1,600 | $800 | $800 |
| **Total** | **$2,400** | **$1,275** | **$475** | **$4,150** | **$2,215** | **$1,935** |

**Key assumptions (conservative):**
- Month-over-month subscriber growth: ~60% (slowing to ~30% by Month 6)
- Subscriber churn: 15%/month
- Bid writer adoption: 5% of active subscribers per month
- Newspaper contributor network: 5 contributors by Month 3
- No grant money included in projections
- No B2B/enterprise deals included

**What could go wrong:**
- Mobile money integration takes longer than expected (PayChangu has occasional downtime)
- Malawian SMEs resist paying for digital services (trust issue)
- MANEPS adoption slower than projected → fewer digital tenders
- Internet connectivity issues affect real-time alerts
- Currency risk: MWK has devalued 40% in 2 years

**What could go right:**
- WhatsApp bot goes viral (procurement professionals share it)
- UNCDF grant ($50–100K) funds 6–12 months of development
- Large NGO signs enterprise deal ($200/month × 12 months = $2,400)
- MANEPS adoption accelerates → flood of new digital tenders
- Word-of-mouth in tight-knit Malawi business community

---

## Payment Platform Details

### PayChangu (PRIMARY — Local MWK)
- **What:** Malawi's leading fintech payment gateway
- **Founded:** ~2020, Lilongwe-based
- **Coverage:** 4,000+ merchants
- **Methods:** Airtel Money, TNM Mpamba, National Bank, FDH Bank, NBS Bank, Visa/Mastercard
- **Fees:** ~3% per transaction
- **Settlement:** T+1 to T+3 (MWK to local bank account)
- **API:** REST with webhooks, checkout page, payment links
- **Integration:** JavaScript SDK + server-side verification
- **Registration:** Online, needs business registration docs
- **Why best for us:** Malawian company, understands local market, supports all mobile money networks

### Stripe (SECONDARY — International USD)
- **What:** Global payment processor
- **Method:** Via Cosmic Phoenix LLC (US entity, EIN 35-2791755, Mercury bank)
- **Fees:** 2.9% + $0.30 per transaction
- **Methods:** Credit/debit cards, Apple Pay, Google Pay
- **Settlement:** T+2 to Mercury bank account
- **Integration:** Stripe Checkout (hosted page) — minimal dev effort
- **Best for:** International NGOs, diaspora Malawians, USD-based organizations

### DPO Pay (BACKUP)
- **What:** Pan-African payment gateway (recently acquired by Network International)
- **Coverage:** 19 African countries including Malawi
- **Office:** Lilongwe (physical presence)
- **Methods:** Mobile money, cards, bank transfers
- **Fees:** Higher than PayChangu (~4-5%)
- **Why backup:** If PayChangu has issues, DPO is the fallback

### Pesapal (BACKUP)
- **What:** East/Southern African payment platform
- **Coverage:** Covers Malawi
- **Integration:** Similar to PayChangu (REST API + webhooks)
- **Why backup:** Good mobile money coverage, but less Malawi-specific than PayChangu

### Payment Decision
**Use Stripe for international + PayChangu for local.** No other platforms needed initially. DPO Pay as fallback only if PayChangu fails.

---

## Scraper Infrastructure Plan

### Why Self-Host (Kill Apify)
| | Apify | Self-Hosted |
|---|---|---|
| Monthly cost | $64+ (was $140 with overages) | $3–15 |
| Control | Limited | Full |
| Malawi site compatibility | Overkill (no anti-bot needed) | Perfect |
| Failure cost | Bills even on 403 errors | $0 on failure |
| Debugging | Black box | Full logs |

### Architecture
```
Request Flow:
1. Cron triggers scraper (every 6h)
2. curl_cffi fetches page (70% of sites)
   └── Fallback: Playwright for JS rendering (MANEPS, World Bank)
3. BeautifulSoup/lxml parses HTML (or JSON for APIs)
4. Dedup against SQLite queue (hash of title + entity + date)
5. Save to src/content/tenders/*.json
6. If new tenders found → build → push → IndexNow

Proxy (only when needed):
- DataImpulse residential ($1/GB)
- Only for: AfDB, UNGM (block cloud IPs)
- Malawi govt sites: NO PROXY NEEDED
```

### Scraper Skills to Build
1. **PDF extraction** — Many tenders are PDF-only (no HTML listing). Use `pdfplumber` or Claude multimodal to extract structured data from PDF tender notices.
2. **Email monitoring** — Some entities send tender notices via email. Set up a dedicated inbox, parse incoming emails.
3. **RSS/Atom feeds** — Some donor sites have feeds. Subscribe and auto-process.
4. **Screenshot monitoring** — For sites that change without clear structure. Take screenshots, compare diffs, extract changes.

### How Scraper Companies Monetize
| Company | Revenue Model | Scale |
|---------|--------------|-------|
| Apify | Compute units + marketplace | $28M ARR |
| ScrapingBee | API calls ($49–599/mo) | B2B |
| Bright Data (Luminati) | Proxy bandwidth ($500+/mo) | Enterprise |
| Outscraper | Per-record pricing ($0.002–0.01) | SMB |
| Zyte (Scrapy Cloud) | Platform + proxy ($150+/mo) | Mid-market |

**Our approach:** We don't sell scraping as a service. We scrape as infrastructure for our AI tender services. The scraping is a cost center, not a revenue center. Keep it as cheap as possible.

---

## Gian Action Items (Ordered by Priority)

### Must Do This Week (Apr 3–10)
1. **Register on PayChangu** — paychangu.com — needs Malawi business docs or Cosmic Phoenix LLC docs
2. **Create GA4 property** for tendersmw.com — give tracking ID to Claude
3. **Cancel Apify Starter plan** — login at console.apify.com, cancel subscription ($29/mo + overages saved)
4. **Confirm the $140 charge source** — check Mercury bank statement, identify which service (Apify? Other?)

### Do This Month (April)
5. **Create WhatsApp Channel** for TendersMW — free, daily tender updates
6. **Send intro email to PPDA** — position as a transparency tool (not competitor)
7. **Send intro email to MCCCI** — explore partnership for member tender alerts
8. **Register WhatsApp Business account** — needed for the OCR bot (Month 2)
9. **Apply to UNCDF Malawi Fintech Challenge** — check application window at apply.uncdf.org
10. **Create Facebook page** for TendersMW — Malawi is Facebook-first

### Nice to Have (When Time Permits)
11. Register Malawi business entity (if PayChangu requires local registration)
12. Open Malawi bank account for MWK settlement
13. Recruit 1–2 newspaper contributors in Blantyre/Lilongwe

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| PayChangu integration delayed | Medium | High | Start registration now; DPO Pay as fallback |
| Low adoption (trust issue) | High | High | Free tier generous; WhatsApp-first; word of mouth |
| MANEPS adoption slow | Medium | Medium | Newspaper moat compensates; multi-source strategy |
| MWK devaluation | High | Medium | USD pricing for international; MWK pricing adjustable |
| Competitor copies our AI features | Low | Medium | Speed + local knowledge + newspaper network = hard to copy |
| Claude API cost spikes | Low | Low | Per-unit costs are tiny ($0.001–0.30); budget caps |
| Scraper breakage (site redesign) | Medium | Low | Multiple sources; alerts on failure; fix within hours |
| Malawi internet reliability | High | Medium | Offline-first design; SMS fallback for critical alerts |

---

## Success Metrics (Monthly Check)

| Metric | Month 2 | Month 4 | Month 6 |
|--------|---------|---------|---------|
| Total tenders | 300+ | 600+ | 1,000+ |
| Data sources | 5 | 7+ | 8+ (incl newspapers) |
| Registered users | 20 | 100 | 250 |
| Paid subscribers | 5–10 | 30–50 | 80–120 |
| Monthly revenue | $50–200 | $500–1,200 | $625–1,500 |
| GSC impressions/week | 1,000+ | 5,000+ | 10,000+ |
| WhatsApp bot users | 10 | 50 | 150 |
| Newspaper tenders/month | 0 | 30 | 100+ |

---

## What We're NOT Doing (And Why)

1. **NOT building a mobile app.** PWA + WhatsApp bot covers mobile. Native app = 2 months of dev for a market that uses WhatsApp, not app stores.
2. **NOT targeting enterprise initially.** Start with SMEs ($10/month) → prove value → upsell enterprise later.
3. **NOT competing on tender volume alone.** malawitenders.com has 1,000+ tenders. We compete on AI intelligence + newspaper exclusives + free tier.
4. **NOT hiring staff.** Everything automated. Claude for AI, crons for scraping, Vercel for hosting. First hire only when revenue exceeds $2,000/month.
5. **NOT expanding regionally until Malawi proves out.** Tanzania/Zambia are tempting. But focus beats breadth.
6. **NOT building our own proxy infrastructure.** DataImpulse at $1/GB is cheap enough. Build vs buy = buy for proxies.
