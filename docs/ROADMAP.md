# genScr roadmap: product, compliance, security

Written 2026-10-24. Positioning: **the clearest descriptive view of every NSE stock**. We explain what the numbers
are and how they compare. We never say what to do. Every idea below is screened against that line.

## 1. Compliance guardrails (apply to every feature)

| Rule | Why | How we enforce it |
|---|---|---|
| No buy/sell/hold, price targets, "top picks", "best", ratings or forecasts | Giving recommendations needs SEBI Research Analyst (2014) or Investment Adviser (2013) registration | `tests/test_compliance_repo.py` scans user-facing text; presets are labelled as example filters |
| Highlights are numeric only ("higher/lower value"), never "better/stronger buy" | A highlight can read as a rating | Section notes on every analytic block |
| No return projections by default; any calculator is historical and caveated | Projections imply expected returns | Gated in code (`test_return_projections_are_off_by_default_and_gated`) |
| No tie-ups with brokers or paid "finfluencers"; no referral links to trading accounts | SEBI's 2024 rules bar registered entities from working with unregistered advice-givers, and a referral link creates a conflict | Policy, not code |
| Exchange data licensing | NSE data is NSE's. A free, non-commercial, end-of-day site on public archives is low risk; **before any monetisation (ads, subscriptions), get an NSE data licence** | Rate limits and noindex on the API discourage bulk redistribution |
| Recent-price rules for "education" sites | SEBI (Jan 2025) limits educators who work with regulated entities to price data at least 3 months old. We are not tied to a regulated entity, but keep the "educational, not advice" framing honest | Review with counsel before any partnership |
| Personal data (DPDP Act 2023) | We collect none: the watchlist lives in the browser, there are no accounts and no trackers | If logins are ever added: consent screen, a grievance officer email (`NEXT_PUBLIC_CONTACT_EMAIL`), deletion on request |
| Trademarks | Company logos are trademarks | Use symbols and names only; credit TradingView for charts (done) |

## 2. Product: what makes genScr different

Shipped:

- **Screener:** colour per metric family, a funnel of how each filter narrows the market, a whole-market histogram per filter, matches vs market medians, and a floating compare tray.
- **Compare:**
  - "What stands out" observations generated from the figures.
  - Split-adjusted 1Y/3Y/5Y chart against the Nifty 50.
  - Volatility, deepest fall (with dates and recovery), beta, and best/worst day.
  - Correlation grid, quarterly revenue and profit, and grouped metrics with relative bars.
- **Markets:** market pulse, i.e. the share of stocks above their 50-day and 200-day averages, distance from 52-week highs, and the same by sector.

Next, ranked by value ÷ effort (all descriptive):

1. **Watchlist as a portfolio lens.** Reuse the compare engine on the whole watchlist: sector mix, how correlated the holdings are, and the combined deepest fall. No allocation suggestions.
2. **How the price moved around past results.** For each stock, the move on the last 8 results days, plus the typical size of that move. It's unique and needs only the `events` and `prices` tables.
3. **Glossary on hover.** One sentence each for beta, drawdown, ROE, Piotroski and the rest, everywhere a metric appears. This is the cheapest way to make the data friendly to beginners.
4. **Screener "what changed".** Which stocks entered or left a saved screen since the last trading day (screens are already shareable by URL).
5. **Valuation vs own history on Compare.** Show each stock's current P/E against its 5-year range. This needs historical EPS, so first run fundamentals-backfill to full coverage.
6. **Shareholding trends.** Promoter, FII, DII and MF changes over 12 quarters, once `shareholding-history` has run (the table is empty today).
7. **Data-quality badges.** Show "results as of Q2 FY27", and mark companies whose fundamentals are missing, so a blank never looks like a zero.

Avoid: composite "scores out of 100" without the formula shown, alerts worded as triggers ("RSI below 30: oversold, buy"),
"stocks like X you should consider", any sorted list titled with "best", "top" or "winners".

## 3. Security

Done in code:

- Rate limit per real client IP. It uses Cloudflare's `CF-Connecting-IP`; previously a forged `X-Forwarded-For` header bypassed the limit.
- API docs and schema are hidden in production.
- Screener input is bounded.
- CORS is restricted to our site and only allows the `Content-Type` header.
- Strict CSP on the site and the API; the site also sends `frame-ancestors 'none'` and COOP.
- The API container runs as a non-root user.
- The site ships no source maps.
- SQL is whitelisted and parameterised everywhere (the screener only accepts known fields and operators).

Owner actions:

1. **Make the GitHub repo private.** This is the only real protection against cloning: today anyone can copy the full code. Render deploys private repos fine.
   - Actions on a private repo get 2,000 free minutes a month. Estimated use is about 1,300: prices ~260, weekly stocks ~40, monthly fundamentals ~180, weekly backfill ~800.
   - Turn off the Saturday backfill once coverage is complete.
2. **Give the API a read-only database role on Neon.** The API never writes, so a bug can't change or delete data. Create the role `genscr_api` in the Neon console (Roles), then run:
   ```sql
   GRANT CONNECT ON DATABASE neondb TO genscr_api;
   GRANT USAGE ON SCHEMA public TO genscr_api;
   GRANT SELECT ON ALL TABLES IN SCHEMA public TO genscr_api;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO genscr_api;
   ALTER ROLE genscr_api SET default_transaction_read_only = on;
   ALTER ROLE genscr_api SET statement_timeout = '15s';
   ```
   Then point Render's `DATABASE_URL` at `genscr_api`. Keep the owner role only in the GitHub secret.
3. **Rotate the Neon owner password** if the connection string was ever pasted into chats, logs or screenshots, then update the GitHub secret.
4. **GitHub:** turn on 2FA, Dependabot alerts, secret scanning and push protection. Protect `main` (no force-push).
5. **Custom domain behind Cloudflare (free plan):** WAF, bot fight mode and DDoS protection in front of both the site and the API. When the domain changes, update `connect-src` in `render.yaml` and `CORS_ORIGINS`.

What can't be prevented: the site's JavaScript and the data it displays always reach the browser, so a determined person
can copy the look or scrape pages slowly. The protections that count are server-side: a private repo, rate limits, a read-only DB
role, and keeping the logic (metrics, screener SQL, insights) on the API rather than in the browser. That's already how genScr works.
