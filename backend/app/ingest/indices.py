"""Load NSE index closes/valuation and index constituents.

    python -m app.ingest.indices                        # last 10 days of closes + constituents
    python -m app.ingest.indices --from 2016-01-01      # backfill closes (one small file per trading day)
    python -m app.ingest.indices --constituents-only
"""

import argparse
import csv
import io
import time
from datetime import date, datetime, timedelta

from app.config import settings
from app.db import connect
from app.ingest.http import client, get_text

CLOSES = "/content/indices/ind_close_all_{d:%d%m%Y}.csv"
# Constituent files published by NSE: display name -> file slug.
CONSTITUENT_FILES = {
    "Nifty 50": "nifty50", "Nifty Next 50": "niftynext50", "Nifty 100": "nifty100", "Nifty 200": "nifty200",
    "Nifty 500": "nifty500", "Nifty Midcap 150": "niftymidcap150", "Nifty Smallcap 250": "niftysmallcap250",
    "Nifty Bank": "niftybank", "Nifty IT": "niftyit", "Nifty Pharma": "niftypharma", "Nifty FMCG": "niftyfmcg",
    "Nifty Auto": "niftyauto", "Nifty Metal": "niftymetal", "Nifty Realty": "niftyrealty", "Nifty Energy": "niftyenergy",
    "Nifty Financial Services": "niftyfinance", "Nifty Media": "niftymedia", "Nifty PSU Bank": "niftypsubank",
    "Nifty Private Bank": "nifty_privatebank", "Nifty Healthcare Index": "niftyhealthcare",
    "Nifty Consumer Durables": "niftyconsumerdurables", "Nifty Oil & Gas": "niftyoilgas",
}

UPSERT = """
INSERT INTO index_prices (index_name, trade_date, open, high, low, close, change_pct, pe, pb, div_yield, turnover_cr)
VALUES (%(index_name)s, %(trade_date)s, %(open)s, %(high)s, %(low)s, %(close)s, %(change_pct)s, %(pe)s, %(pb)s,
        %(div_yield)s, %(turnover_cr)s)
ON CONFLICT (index_name, trade_date) DO UPDATE SET
    open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low, close = EXCLUDED.close,
    change_pct = EXCLUDED.change_pct, pe = EXCLUDED.pe, pb = EXCLUDED.pb, div_yield = EXCLUDED.div_yield,
    turnover_cr = EXCLUDED.turnover_cr
"""


def _num(v: str | None) -> float | None:
    v = (v or "").strip().replace(",", "")
    if not v or v in ("-", "NA"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def parse_closes(text: str) -> list[dict]:
    rows = []
    for r in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
        name, close = r.get("Index Name"), _num(r.get("Closing Index Value"))
        if not name or close is None:
            continue
        rows.append({
            "index_name": name,
            "trade_date": datetime.strptime(r["Index Date"], "%d-%m-%Y").date(),
            "open": _num(r.get("Open Index Value")), "high": _num(r.get("High Index Value")),
            "low": _num(r.get("Low Index Value")), "close": close, "change_pct": _num(r.get("Change(%)")),
            "pe": _num(r.get("P/E")), "pb": _num(r.get("P/B")), "div_yield": _num(r.get("Div Yield")),
            "turnover_cr": _num(r.get("Turnover (Rs. Cr.)")),
        })
    return rows


def parse_constituents(text: str) -> list[str]:
    return [r["Symbol"].strip() for r in csv.DictReader(io.StringIO(text.lstrip("﻿"))) if r.get("Symbol")]


def load_closes(start: date, end: date, skip_existing: bool = True, trading_days_only: bool = False) -> int:
    """trading_days_only: fetch only dates present in `prices` (fast backfill; includes special sessions)."""
    loaded = 0
    with connect() as conn, client() as http:
        existing = set()
        if skip_existing:
            existing = {r["d"] for r in conn.execute(
                "SELECT DISTINCT trade_date AS d FROM index_prices WHERE trade_date BETWEEN %s AND %s", (start, end))}
        wanted = None
        if trading_days_only:
            wanted = {r["d"] for r in conn.execute(
                "SELECT DISTINCT trade_date AS d FROM prices WHERE trade_date BETWEEN %s AND %s", (start, end))}
        d = start
        while d <= end:
            if d not in existing and (wanted is None or d in wanted):
                text = get_text(http, settings.nse_archive_base + CLOSES.format(d=d))
                if text:
                    rows = parse_closes(text)
                    with conn.cursor() as cur:
                        cur.executemany(UPSERT, rows)
                    conn.commit()
                    loaded += 1
                    print(f"{d}: {len(rows)} indices", flush=True)
                time.sleep(settings.request_delay_seconds)
            d += timedelta(days=1)
    return loaded


def load_constituents() -> int:
    total = 0
    with connect() as conn, client() as http:
        for name, slug in CONSTITUENT_FILES.items():
            text = get_text(http, f"{settings.nse_archive_base}/content/indices/ind_{slug}list.csv")
            time.sleep(settings.request_delay_seconds)
            if not text:
                print(f"{name}: no constituent file")
                continue
            symbols = parse_constituents(text)
            if not symbols:
                continue
            conn.execute("DELETE FROM index_constituents WHERE index_name = %s", (name,))
            with conn.cursor() as cur:
                cur.executemany("INSERT INTO index_constituents (index_name, symbol) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                                [(name, s) for s in symbols])
            conn.commit()
            total += len(symbols)
            print(f"{name}: {len(symbols)} constituents")
    return total


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--from", dest="start", type=date.fromisoformat, default=date.today() - timedelta(days=10))
    p.add_argument("--to", dest="end", type=date.fromisoformat, default=date.today())
    p.add_argument("--constituents-only", action="store_true")
    p.add_argument("--trading-days-only", action="store_true", help="only dates that exist in prices (backfills)")
    a = p.parse_args()
    if not a.constituents_only:
        print(f"index closes: {load_closes(a.start, a.end, trading_days_only=a.trading_days_only)} days loaded")
    print(f"constituents: {load_constituents()} memberships")


if __name__ == "__main__":
    main()
