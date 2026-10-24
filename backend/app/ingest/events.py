"""Load upcoming board meetings and results dates from NSE's event calendar into `events`.

    python -m app.ingest.events                              # 30 days back to 90 days ahead (daily job)
    python -m app.ingest.events --from 2026-01-01 --to 2026-03-31

Dates and agendas are as announced by the companies and can change. Each run replaces the stored rows
for its window, so a meeting that NSE drops (cancelled, or moved to another date) disappears.
"""

import argparse
import re
from collections import Counter
from datetime import date, timedelta

from app.db import connect
from app.ingest.results import SITE, NseClient, _date

URL = SITE + "/api/event-calendar?index=equities&from_date={start:%d-%m-%Y}&to_date={end:%d-%m-%Y}"
CATEGORIES = ("results", "dividend", "fund_raising", "other")
COLUMNS = ["symbol", "event_date", "purpose", "description"]
UPSERT = f"""
INSERT INTO events ({", ".join(COLUMNS)})
VALUES ({", ".join(f"%({c})s" for c in COLUMNS)})
ON CONFLICT (symbol, event_date, purpose) DO UPDATE SET description = EXCLUDED.description
"""
# Keyed by (symbol, event_date, purpose), so the window delete can match on the same columns.
DELETE_STALE = """
DELETE FROM events e
WHERE e.event_date BETWEEN %(start)s AND %(end)s
  AND NOT EXISTS (
      SELECT 1 FROM unnest(%(symbols)s::text[], %(dates)s::date[], %(purposes)s::text[]) AS k(symbol, event_date, purpose)
      WHERE k.symbol = e.symbol AND k.event_date = e.event_date AND k.purpose = e.purpose)
"""
DAYS_BACK, DAYS_AHEAD = 30, 90
_CANCELLED = re.compile(r"\bcancel", re.IGNORECASE)


def categories(purpose: str | None) -> list[str]:
    """NSE joins agenda items with '/': 'Financial Results/Dividend/Other business matters' -> ['results', 'dividend'].

    Anything that is not results, dividend or fund raising is 'other', and only when nothing else matched,
    so 'Other business matters' or 'Board meeting Rescheduled' alone both become 'other'.
    """
    found: list[str] = []
    for part in (purpose or "").lower().split("/"):
        part = part.strip()
        if "result" in part:
            cat = "results"
        elif "dividend" in part:
            cat = "dividend"
        elif "fund raising" in part:
            cat = "fund_raising"
        else:
            continue
        if cat not in found:
            found.append(cat)
    return found or ["other"]


def _maybe_date(v):
    if not v:
        return None
    try:
        return _date(v)
    except (TypeError, ValueError):
        return None


def to_rows(records: list[dict]) -> list[dict]:
    """NSE records -> one row per (symbol, event_date, category).

    NSE repeats a meeting when it is revised. The first non-empty agenda text is kept. A date that has a
    cancellation notice is dropped for that symbol, since the meeting will not take place on that day.
    """
    rows: dict[tuple, dict] = {}
    cancelled: set[tuple] = set()
    for r in records:
        symbol = (r.get("symbol") or "").strip().upper()
        day = _maybe_date(r.get("date"))
        if not symbol or not day:
            continue
        desc = " ".join((r.get("bm_desc") or "").split()) or None
        if desc and _CANCELLED.search(desc):
            cancelled.add((symbol, day))
            continue
        for cat in categories(r.get("purpose")):
            key = (symbol, day, cat)
            row = rows.get(key)
            if row is None:
                rows[key] = {"symbol": symbol, "event_date": day, "purpose": cat, "description": desc}
            elif row["description"] is None:
                row["description"] = desc
    return [r for k, r in rows.items() if (k[0], k[1]) not in cancelled]


def load_range(start: date, end: date) -> int:
    nse = NseClient()
    try:
        records = nse.json(URL.format(start=start, end=end))
    finally:
        nse.close()
    if not isinstance(records, list):
        raise ValueError(f"Unexpected event-calendar response: {type(records).__name__}")
    rows = to_rows(records)
    with connect() as conn:
        with conn.cursor() as cur:
            if rows:
                cur.executemany(UPSERT, rows)
            if records:  # an empty response could be NSE refusing us: keep what we have
                cur.execute(DELETE_STALE, {
                    "start": start, "end": end,
                    "symbols": [r["symbol"] for r in rows],
                    "dates": [r["event_date"] for r in rows],
                    "purposes": [r["purpose"] for r in rows],
                })
        conn.commit()
    counts = Counter(r["purpose"] for r in rows)
    print(f"events {start} .. {end}: {len(records)} NSE records -> {len(rows)} rows {dict(counts)}")
    return len(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    today = date.today()
    p.add_argument("--from", dest="start", type=date.fromisoformat, default=today - timedelta(days=DAYS_BACK))
    p.add_argument("--to", dest="end", type=date.fromisoformat, default=today + timedelta(days=DAYS_AHEAD))
    a = p.parse_args()
    load_range(a.start, a.end)


if __name__ == "__main__":
    main()
