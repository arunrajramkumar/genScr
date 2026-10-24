"""Load NSE corporate actions (dividends, bonuses, splits, ...) into `corporate_actions`.

    python -m app.ingest.corporate_actions                       # last 15 days (daily job)
    python -m app.ingest.corporate_actions --from 2005-01-01     # full backfill, ~250 monthly requests

Uses NSE's all-symbols query by date window, so a backfill is one request per month, not per company.
"""

import argparse
from collections import defaultdict
from datetime import date, timedelta

from app.db import connect
from app.ingest.corporate_actions_parser import parse_subject
from app.ingest.results import SITE, NseClient, _date

URL = SITE + "/api/corporates-corporateActions?index=equities&from_date={start:%d-%m-%Y}&to_date={end:%d-%m-%Y}"
COLUMNS = [
    "symbol", "ex_date", "kind", "amount", "ratio_new", "ratio_held", "old_fv", "new_fv", "price", "record_date", "subject",
]
UPSERT = f"""
INSERT INTO corporate_actions ({", ".join(COLUMNS)})
VALUES ({", ".join(f"%({c})s" for c in COLUMNS)})
ON CONFLICT (symbol, ex_date, kind) DO UPDATE SET
    {", ".join(f"{c} = EXCLUDED.{c}" for c in COLUMNS[3:])}
"""


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _maybe_date(v):
    try:
        return _date(v)
    except (TypeError, ValueError):
        return None


def to_rows(records: list[dict]) -> list[dict]:
    """NSE records -> one row per (symbol, ex_date, kind); same-day dividends are summed."""
    rows: dict[tuple, dict] = {}
    for r in records:
        ex = _maybe_date(r.get("exDate"))
        if not ex or not r.get("symbol"):
            continue
        for ev in parse_subject(r.get("subject", ""), _num(r.get("faceVal"))):
            key = (r["symbol"], ex, ev["kind"])
            row = rows.get(key)
            if row and ev["kind"] == "dividend":
                row["amount"] = round(row["amount"] + ev["amount"], 4)
                row["subject"] = f"{row['subject']} | {r['subject'].strip()}"
                continue
            rows[key] = {
                **dict.fromkeys(COLUMNS), **{k: v for k, v in ev.items() if k != "kind"},
                "symbol": r["symbol"], "ex_date": ex, "kind": ev["kind"],
                "record_date": _maybe_date(r.get("recDate")), "subject": " ".join(r.get("subject", "").split()),
            }
    return list(rows.values())


def windows(start: date, end: date, days: int = 31):
    d = start
    while d <= end:
        yield d, min(d + timedelta(days=days - 1), end)
        d += timedelta(days=days)


def load_range(start: date, end: date) -> int:
    total = 0
    nse = NseClient()
    try:
        with connect() as conn:
            for a, b in windows(start, end):
                records = nse.json(URL.format(start=a, end=b)) or []
                rows = to_rows(records)
                if rows:
                    with conn.cursor() as cur:
                        cur.executemany(UPSERT, rows)
                    conn.commit()
                total += len(rows)
                kinds = defaultdict(int)
                for r in rows:
                    kinds[r["kind"]] += 1
                print(f"{a} .. {b}: {len(records)} records -> {dict(kinds)}", flush=True)
    finally:
        nse.close()
    print(f"corporate_actions: {total} rows upserted")
    return total


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--from", dest="start", type=date.fromisoformat, default=date.today() - timedelta(days=15))
    p.add_argument("--to", dest="end", type=date.fromisoformat, default=date.today())
    a = p.parse_args()
    load_range(a.start, a.end)


if __name__ == "__main__":
    main()
