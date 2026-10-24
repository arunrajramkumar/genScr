"""Load NSE end-of-day bhavcopy files into `prices`.

    python -m app.ingest.bhavcopy                       # latest trading day
    python -m app.ingest.bhavcopy --date 2026-10-22
    python -m app.ingest.bhavcopy --from 2016-01-01 --to 2026-10-22 --skip-existing
"""

import argparse
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import settings
from app.db import connect
from app.ingest.http import client, get_text
from app.ingest.parsers import parse_bhavcopy

UDIFF_START = date(2024, 7, 8)

UPSERT = """
INSERT INTO prices (symbol, trade_date, series, open, high, low, close, prev_close, volume, turnover, trades)
VALUES (%(symbol)s, %(trade_date)s, %(series)s, %(open)s, %(high)s, %(low)s, %(close)s,
        %(prev_close)s, %(volume)s, %(turnover)s, %(trades)s)
ON CONFLICT (symbol, trade_date) DO UPDATE SET
    series = EXCLUDED.series, open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
    close = EXCLUDED.close, prev_close = EXCLUDED.prev_close, volume = EXCLUDED.volume,
    turnover = EXCLUDED.turnover, trades = EXCLUDED.trades
"""


def bhavcopy_url(d: date) -> str:
    base = settings.nse_archive_base
    if d >= UDIFF_START:
        return f"{base}/content/cm/BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
    mon = d.strftime("%b").upper()
    return f"{base}/content/historical/EQUITIES/{d:%Y}/{mon}/cm{d:%d}{mon}{d:%Y}bhav.csv.zip"


def ist_today() -> date:
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


def load_range(start: date, end: date, skip_existing: bool = False) -> int:
    loaded_days = 0
    with connect() as conn, client() as http:
        existing = set()
        if skip_existing:
            existing = {
                r["trade_date"]
                for r in conn.execute(
                    "SELECT DISTINCT trade_date FROM prices WHERE trade_date BETWEEN %s AND %s", (start, end)
                )
            }
        d = start
        while d <= end:
            # Weekends are checked too: NSE holds special sessions (Diwali Muhurat, Budget day, live drills).
            if d not in existing:
                text = get_text(http, bhavcopy_url(d))
                if text is None:
                    if d.weekday() < 5:
                        print(f"{d}: no file (holiday or not yet published)")
                else:
                    rows = parse_bhavcopy(text)
                    with conn.cursor() as cur:
                        cur.executemany(UPSERT, rows)
                    conn.commit()
                    loaded_days += 1
                    print(f"{d}: {len(rows)} rows")
                time.sleep(settings.request_delay_seconds)
            d += timedelta(days=1)
    return loaded_days


def load_latest(lookback_days: int = 5) -> int:
    """Load any missing days in the last few days (covers holidays and late publishing)."""
    today = ist_today()
    return load_range(today - timedelta(days=lookback_days), today, skip_existing=True)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--date", type=date.fromisoformat)
    p.add_argument("--from", dest="start", type=date.fromisoformat)
    p.add_argument("--to", dest="end", type=date.fromisoformat)
    p.add_argument("--skip-existing", action="store_true")
    p.add_argument("--lookback", type=int, default=5, help="Days to check when loading the latest (default 5)")
    a = p.parse_args()

    if a.date:
        load_range(a.date, a.date)
    elif a.start:
        load_range(a.start, a.end or ist_today(), a.skip_existing)
    else:
        load_latest(a.lookback)


if __name__ == "__main__":
    main()
