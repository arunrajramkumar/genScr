"""Load financials from a CSV (see data/fundamentals_template.csv). Amounts in ₹ crore.

    python -m app.ingest.fundamentals_csv path/to/file.csv

Use this until the XBRL parser (roadmap) lands. Only load data you have the right to use,
e.g. numbers transcribed from a company's own published results.
"""

import argparse
import csv

from app.db import connect
from app.ingest.parsers import _int, _num, _parse_date

NUMERIC = [
    "revenue", "operating_profit", "depreciation", "interest", "pbt", "net_profit", "eps",
    "total_assets", "total_equity", "reserves", "total_debt", "current_assets",
    "current_liabilities", "cash", "cfo", "capex",
]
COLUMNS = ["symbol", "period_end", "period_type", *NUMERIC, "shares_outstanding", "source"]

UPSERT = f"""
INSERT INTO fundamentals ({", ".join(COLUMNS)})
VALUES ({", ".join(f"%({c})s" for c in COLUMNS)})
ON CONFLICT (symbol, period_end, period_type) DO UPDATE SET
    {", ".join(f"{c} = EXCLUDED.{c}" for c in COLUMNS[3:])}
"""


def parse_row(r: dict) -> dict:
    row = {
        "symbol": r["symbol"].strip().upper(),
        "period_end": _parse_date(r["period_end"]),
        "period_type": r["period_type"].strip().upper(),
        "shares_outstanding": _int(r.get("shares_outstanding")),
        "source": (r.get("source") or "csv").strip(),
    }
    row.update({c: _num(r.get(c)) for c in NUMERIC})
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path")
    a = p.parse_args()

    with open(a.path, newline="", encoding="utf-8") as f:
        rows = [parse_row(r) for r in csv.DictReader(f) if r.get("symbol") and not r["symbol"].startswith("#")]
    with connect() as conn, conn.cursor() as cur:
        cur.executemany(UPSERT, rows)
        conn.commit()
    print(f"fundamentals: {len(rows)} rows upserted")


if __name__ == "__main__":
    main()
