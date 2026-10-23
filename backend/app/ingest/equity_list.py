"""Refresh the `stocks` master list and sectors from NSE public CSVs.

    python -m app.ingest.equity_list
"""

from app.config import settings
from app.db import connect
from app.ingest.http import client, get_text
from app.ingest.parsers import parse_equity_list, parse_index_constituents

EQUITY_LIST = "/content/equities/EQUITY_L.csv"
SECTOR_SOURCE = "/content/indices/ind_nifty500list.csv"

UPSERT = """
INSERT INTO stocks (symbol, isin, name, series, listing_date, face_value, updated_at)
VALUES (%(symbol)s, %(isin)s, %(name)s, %(series)s, %(listing_date)s, %(face_value)s, now())
ON CONFLICT (symbol) DO UPDATE SET
    isin = EXCLUDED.isin, name = EXCLUDED.name, series = EXCLUDED.series,
    listing_date = EXCLUDED.listing_date, face_value = EXCLUDED.face_value, updated_at = now()
"""


def main():
    base = settings.nse_archive_base
    with connect() as conn, client() as http:
        text = get_text(http, base + EQUITY_LIST)
        if not text:
            raise SystemExit("Could not download EQUITY_L.csv")
        stocks = parse_equity_list(text)
        with conn.cursor() as cur:
            cur.executemany(UPSERT, stocks)
        print(f"stocks: {len(stocks)} upserted")

        sectors = parse_index_constituents(get_text(http, base + SECTOR_SOURCE) or "")
        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE stocks SET sector = %(sector)s WHERE symbol = %(symbol)s", sectors
            )
        print(f"sectors: {len(sectors)} tagged (Nifty 500 constituents)")
        conn.commit()


if __name__ == "__main__":
    main()
