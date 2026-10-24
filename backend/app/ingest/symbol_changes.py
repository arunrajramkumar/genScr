"""Stitch history across ticker renames (e.g. ZOMATO -> ETERNAL) using NSE's symbol-change list.

    python -m app.ingest.symbol_changes

Copies rows recorded under the old symbol to the new one where the new symbol has no row for that
date/period (prices, corporate actions, fundamentals). Idempotent; safe to run daily.
"""

import csv
import io
from datetime import datetime

from app.config import settings
from app.db import connect
from app.ingest.http import client, get_text

URL = "/content/equities/symbolchange.csv"


def parse(text: str) -> list[dict]:
    out = []
    for r in csv.reader(io.StringIO(text.lstrip("﻿"))):
        if len(r) < 4 or r[1].strip().upper() == "OLD SYMBOL":
            continue
        try:
            d = datetime.strptime(r[3].strip().title(), "%d-%b-%Y").date()
        except ValueError:
            continue
        old, new = r[1].strip(), r[2].strip()
        if old and new and old != new:
            out.append({"old_symbol": old, "new_symbol": new, "effective_date": d})
    return out


# Only rows BEFORE the rename date are copied: NSE can later reuse the old ticker for another company.
MERGES = [
    """INSERT INTO prices (symbol, trade_date, series, open, high, low, close, prev_close, volume, turnover, trades)
       SELECT %(new)s, trade_date, series, open, high, low, close, prev_close, volume, turnover, trades
       FROM prices WHERE symbol = %(old)s AND trade_date < %(date)s
       ON CONFLICT (symbol, trade_date) DO NOTHING""",
    """INSERT INTO corporate_actions
           (symbol, ex_date, kind, amount, ratio_new, ratio_held, old_fv, new_fv, price, record_date, subject)
       SELECT %(new)s, ex_date, kind, amount, ratio_new, ratio_held, old_fv, new_fv, price, record_date, subject
       FROM corporate_actions WHERE symbol = %(old)s AND ex_date < %(date)s
       ON CONFLICT (symbol, ex_date, kind) DO NOTHING""",
]


def main():
    with client() as http:
        text = get_text(http, settings.nse_archive_base + URL)
    if not text:
        raise SystemExit("Could not download symbolchange.csv")
    changes = sorted(parse(text), key=lambda c: c["effective_date"])  # oldest first handles chains A->B->C
    with connect() as conn:
        with conn.cursor() as cur:
            cur.executemany("INSERT INTO symbol_changes VALUES (%(old_symbol)s, %(new_symbol)s, %(effective_date)s) "
                            "ON CONFLICT DO NOTHING", changes)
        merged = 0
        held = {r["symbol"] for r in conn.execute("SELECT DISTINCT symbol FROM prices")}
        for c in changes:
            if c["old_symbol"] not in held:
                continue
            for sql in MERGES:
                args = {"old": c["old_symbol"], "new": c["new_symbol"], "date": c["effective_date"]}
                merged += conn.execute(sql, args).rowcount
            held.add(c["new_symbol"])
        conn.commit()
    print(f"symbol changes: {len(changes)} listed, {merged} rows stitched onto new symbols")


if __name__ == "__main__":
    main()
