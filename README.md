# genScr: Indian Stock Screener & Analytics

A fast, transparent stock screener for NSE-listed companies: search, screen, analyse and compare stocks using **free, legitimate public data** (NSE end-of-day files plus company disclosures).

> **Not investment advice.** genScr shows data and analytics for education only. It is not a SEBI-registered investment adviser or research analyst and makes no buy/sell recommendations.

## Features (v0.1)

| Area | What you get |
|---|---|
| **Search** | Typo-tolerant search by symbol or company name (Postgres trigram). Press `/` anywhere to search. |
| **Market overview** | Breadth (advances/declines, 52W highs and lows), top gainers and losers, most active by turnover, sector heatmap |
| **Stock page** | Split/bonus-adjusted area or candle chart with 50/200 DMA and OHLC hover readout, signal chips, valuation and return ratios, Piotroski F-score, Altman Z'', RSI, sector peers, annual and quarterly financials |
| **Past returns** | ₹10k N years ago with real share counts: shares bought, bonus/split shares, every dividend; price-only vs dividends as cash vs reinvested, with a full event ledger |
| **Dividend history** | Every payment since 2005, yield at the time, per-FY bars restated for bonuses/splits, paying and growth streaks, 5-year dividend CAGR |
| **Where it stands** | Percentile rank vs sector peers and all NSE stocks on 12 metrics (ROE, margins, growth, P/E, debt, yield, returns, size) |
| **Risk & seasonality** | Worst drawdowns with recovery time, distance from peak, volatility, up-days %, underwater chart, calendar-year returns, monthly heatmap |
| **Company journey** | Animated timeline: listing, bonuses, splits, rights, buybacks, demergers, yearly dividends, record high and deepest fall, each with its source |
| **Did you know?** | Rotating facts per stock computed only from filings, NSE prices and the listing record, each with its source (profit per day, best/worst day, winning streaks, debt-free, sector rank…) |
| **Price CAGR & dividends** | 1–5 year annualised price growth per stock; trailing dividend yield from the annual cash-flow statement (also in screener and compare) |
| **What-if calculator** | One-time or monthly SIP, any amount, 1–N years slider: value, gain, CAGR/XIRR, growth chart |
| **5-year outlook** | Bear/base/bull CAGR *scenarios* from historical price CAGR, profit CAGR and volatility (clearly labelled: not a forecast) |
| **Screener** | Plain query language (`roe > 18 and debt_to_equity < 0.5`), presets, sortable results, sector filter, shareable links, results summary |
| **Compare** | 2–5 stocks side by side, 1-year performance, ₹10k true-return race (dividends included), percentile radar, category leads |

## Architecture

```
web/  (Next.js 15 + Tailwind + lightweight-charts)  ──►  backend/ (FastAPI)  ──►  PostgreSQL + TimescaleDB
                                                          ▲
                              backend/app/ingest (scheduler: NSE bhavcopy, stock list, metrics)
```

- `db/init.sql`: schema (`stocks`, `prices` hypertable, `fundamentals`, `stock_metrics`)
- `backend/app/ingest/`: data loaders. Pure parsers live in `parsers.py` and are unit-tested against the real NSE formats.
- `backend/app/services/`: indicators, quality scores, split/bonus adjustment, safe screener SQL builder
- `stock_metrics` is rebuilt nightly, so screener queries hit one indexed table and stay fast

## Quick start

Prerequisites: Docker (or Rancher Desktop), Make.

```bash
cp .env.example .env
make up                      # db, api (:8000), scheduler, web (:3000)
make ingest                  # stock list + latest bhavcopy + metrics (~1 minute)
make backfill FROM=2025-01-01   # optional: price history for charts, returns, RSI, 52W range
```

Open http://localhost:3000. API docs are at http://localhost:8000/docs.

**Local development without Docker for the app code:**

```bash
docker compose up -d db
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
uvicorn app.main:app --reload          # API on :8000
cd ../web && npm install && npm run dev   # web on :3000
```

## Data sources & legality

| Data | Source | Notes |
|---|---|---|
| EOD prices | NSE bhavcopy (`nsearchives.nseindia.com/content/cm/…`) | Fetched **once per trading day**, cached in Postgres. Both the current UDiFF and pre-July-2024 formats are supported. |
| Stock list | NSE `EQUITY_L.csv` | Weekly refresh |
| Sectors | NSE Nifty 500 constituent file | Covers Nifty 500 names; others show no sector |
| Corporate actions | NSE corporate actions (`app.ingest.corporate_actions`), all symbols by monthly window from 2005, parsed from free-text subjects | Daily job loads the last 15 days |
| Fundamentals | Companies' financial-results XBRL filings (`app.ingest.results`) | Legacy and SEBI Integrated Filing formats, consolidated preferred, banks supported. Filing indexes come from NSE's website API, so run quarterly at a low request rate. CSV loader is also available. |

Ground rules: never scrape NSE pages per user request, keep request rates low, label prices as end-of-day, and don't publish buy/sell calls. Before commercial launch, confirm redistribution terms with NSE Data & Analytics.

## Fundamentals

Ratios (P/E, ROE, ROCE, D/E, Piotroski, Altman Z'') come from company filings:

```bash
python -m app.ingest.results --symbols TCS,INFY            # a few companies (~8 requests each)
python -m app.ingest.results --universe nifty500 --skip-existing   # ~1-2 hours, resumable
python -m app.ingest.compute_metrics
```

Or load your own CSV in the `data/fundamentals_template.csv` format: `make fundamentals FILE=data/my.csv`.

## Compliance guardrails

genScr is built to stay an **information tool**, not an adviser (SEBI Research Analyst / Investment Adviser rules, DPDP Act, IT Act, NSE data terms):

- **No advice language:** `app/services/compliance.py` flags recommendation, price-target, tip and assured-return wording (pattern list in that file). Generated facts are filtered through it at runtime, and `tests/test_compliance_repo.py` scans every user-facing file so CI fails on violations.
- **Disclaimers:** one shared text (`web/src/lib/site.ts`) in the footer of every page, a first-visit notice, and Disclaimer / Terms / Privacy pages. Inline notes on the screener, compare, calculator and facts.
- **No return projections by default:** the 5-year outlook renders only with `NEXT_PUBLIC_ENABLE_PROJECTIONS=true`. Get legal advice before enabling it.
- **Neutral presentation:** factual preset names, RSI shown without buy/sell colours, compare highlights aren't a "winner".
- **Data terms:** end-of-day only, source attribution, stale-data banner, per-IP API rate limit (bulk redistribution), `noindex` API, minimum 1 s between NSE requests.
- **Security headers** on web and API.

**Before public launch:** set `NEXT_PUBLIC_CONTACT_EMAIL`, have a lawyer review the legal pages, and check your employer's side-project policy.

## Roadmap

1. TTM (trailing-twelve-month) ratios from quarterly results; dividends in total-return calculations
2. Shareholding patterns, promoter pledges, insider trades (SAST/PIT), bulk and block deals
3. Corporate announcements feed, plus AI summaries of results and concalls with source citations
4. Natural-language screener ("debt-free IT companies growing 20%") that translates to the query language
5. Screen backtesting, reverse DCF, valuation bands
6. Watchlists and alerts (auth), optional broker login for live prices (each user's own API session)
7. BSE coverage, F&O analytics

## Deploying

**Free-tier layout (fast and cheap):** the website is a **static export** (`STATIC_EXPORT=1`) on a Render Static Site: global CDN, never sleeps, no instance hours. Only the API is a (free) instance; point a free uptime monitor (e.g. UptimeRobot, 5-minute interval) at `/api/health` to keep it warm. The API caches finished JSON responses in memory and clears them automatically when the nightly data update lands.

**Seed the hosted database from your local one.** Don't backfill from scratch in the cloud: it takes hours, and NSE often blocks datacenter IPs.

```bash
make export-data                                     # local db -> data/export/*.csv.gz (~60 MB)
make import-data TARGET_URL='postgresql://…?sslmode=require'   # schema + data into the hosted db (needs psql)
```

**Can't reach the database from your network** (e.g. a corporate proxy)? Let GitHub Actions build and load it. Nothing is uploaded from your machine:

1. Repo → Settings → Secrets and variables → Actions → add `RENDER_DATABASE_URL` (Render's External Database URL).
2. Actions → **Seed hosted database** → Run workflow → pick the start date and fundamentals, then type `REPLACE`.

The runner downloads everything from NSE into a temporary Postgres, computes the metrics, then copies the tables into Render. Expect ~40 min for prices since 2021, plus ~2 h for Nifty 500 fundamentals.

**Keeping it fresh for free:** the **Data update** workflow (`.github/workflows/daily-update.yml`) runs on GitHub's schedule using the same `RENDER_DATABASE_URL` secret: prices + metrics at 20:00 IST Mon–Fri (retry at 22:00), stock list on Sundays, results filings monthly. You can also run it by hand from the Actions tab.

After seeding, the scheduler only adds each new trading day (`bhavcopy.load_latest` skips dates already loaded). Run the quarterly fundamentals refresh (`app.ingest.results --skip-existing`) from your own machine with `DATABASE_URL` pointed at the hosted database, because NSE's website API tends to reject cloud IPs.


- **Web:** Vercel (set `NEXT_PUBLIC_API_URL`)
- **API + scheduler:** Render / Railway / Fly.io (or AWS `ap-south-1`), built from `backend/Dockerfile`
- **DB:** Timescale Cloud, or any Postgres with the TimescaleDB extension
- **Domain:** Cloudflare Registrar plus Cloudflare DNS/CDN, and set `CORS_ORIGINS` to your domain

## License

MIT. See [LICENSE](LICENSE).
