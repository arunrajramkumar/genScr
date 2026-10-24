"""Load NSE delivery figures (share of traded quantity taken for delivery) into `prices`.

Source: NSE sec_bhavdata_full_DDMMYYYY.csv, one file per trading day. Only dates already in `prices`
are fetched, so run app.ingest.bhavcopy first.

    python -m app.ingest.delivery                       # last 5 days, days still missing a figure
    python -m app.ingest.delivery --lookback 10
    python -m app.ingest.delivery --date 2026-10-22
    python -m app.ingest.delivery --from 2025-10-01 --to 2026-10-22
"""

import argparse
import csv
import io
import time
from datetime import date, datetime, timedelta

from app.config import settings
from app.db import connect
from app.ingest.bhavcopy import ist_today
from app.ingest.http import client, get_text

# Delivery is reported for the regular and trade-for-trade series (the EQ/BE rows of prices).
DELIVERY_SERIES = frozenset({"EQ", "BE"})

STAGE = """
CREATE TEMP TABLE delivery_stage (
    symbol TEXT, trade_date DATE, deliv_qty BIGINT, deliv_pct NUMERIC(6, 2)
) ON COMMIT DROP
"""

APPLY = """
UPDATE prices p SET deliv_qty = s.deliv_qty, deliv_pct = s.deliv_pct
FROM delivery_stage s
WHERE p.symbol = s.symbol AND p.trade_date = s.trade_date AND p.trade_date = %s
  AND p.series IN ('EQ', 'BE')
"""


def delivery_url(d: date) -> str:
    return f"{settings.nse_archive_base}/products/content/sec_bhavdata_full_{d:%d%m%Y}.csv"


def _num(v: str | None) -> float | None:
    v = (v or "").strip().replace(",", "")
    if not v or v in ("-", "NA"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def parse_delivery(text: str) -> list[dict]:
    """EQ and BE rows of a sec_bhavdata_full file. Headers and cells can carry padding spaces ("SYMBOL, SERIES, ...")."""
    rows = []
    for raw in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        r = {(k or "").strip(): (v or "").strip() for k, v in raw.items()}
        if r.get("SERIES") not in DELIVERY_SERIES:
            continue
        qty = _num(r.get("DELIV_QTY"))
        rows.append({
            "symbol": r["SYMBOL"],
            "trade_date": datetime.strptime(r["DATE1"], "%d-%b-%Y").date(),
            "deliv_qty": int(qty) if qty is not None else None,
            "deliv_pct": _num(r.get("DELIV_PER")),
        })
    return rows


def _apply(conn, day: date, rows: list[dict]) -> int:
    """Stage one day's figures with COPY, then update prices in a single statement."""
    with conn.cursor() as cur:
        cur.execute(STAGE)
        with cur.copy("COPY delivery_stage (symbol, trade_date, deliv_qty, deliv_pct) FROM STDIN") as cp:
            for r in rows:
                cp.write_row((r["symbol"], r["trade_date"], r["deliv_qty"], r["deliv_pct"]))
        cur.execute(APPLY, (day,))
        updated = cur.rowcount
    conn.commit()
    return updated


def load_range(start: date, end: date, skip_existing: bool = True) -> int:
    """Fetch delivery for each trading day in [start, end] that `prices` holds.

    skip_existing: leave out days that already have an EQ figure (each day is written in one commit,
    so a day is either fully loaded or not at all). NSE shows "-" for every BE row, so BE gaps are normal.
    """
    loaded = 0
    with connect() as conn, client() as http:
        days = [r["d"] for r in conn.execute(
            """
            SELECT trade_date AS d FROM prices
            WHERE trade_date BETWEEN %s AND %s AND series IN ('EQ', 'BE')
            GROUP BY trade_date
            HAVING NOT %s OR NOT bool_or(series = 'EQ' AND deliv_pct IS NOT NULL)
            ORDER BY d
            """,
            (start, end, skip_existing),
        )]
        for d in days:
            text = get_text(http, delivery_url(d))
            if text is None:
                print(f"{d}: no file (not yet published)", flush=True)
            else:
                rows = parse_delivery(text)
                print(f"{d}: {_apply(conn, d, rows)} prices rows updated", flush=True)
                loaded += 1
            time.sleep(settings.request_delay_seconds)
    return loaded


def load_latest(lookback_days: int = 5) -> int:
    """Fill delivery for the last few days (covers late publishing)."""
    today = ist_today()
    return load_range(today - timedelta(days=lookback_days), today)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--date", type=date.fromisoformat)
    p.add_argument("--from", dest="start", type=date.fromisoformat)
    p.add_argument("--to", dest="end", type=date.fromisoformat)
    p.add_argument("--lookback", type=int, default=5, help="Days to check when loading the latest (default 5)")
    a = p.parse_args()

    if a.date:
        load_range(a.date, a.date, skip_existing=False)
    elif a.start:
        load_range(a.start, a.end or ist_today())
    else:
        load_latest(a.lookback)


if __name__ == "__main__":
    main()
