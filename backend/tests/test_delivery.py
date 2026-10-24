from datetime import date

from app.ingest.delivery import delivery_url, parse_delivery

# Same layout as NSE's sec_bhavdata_full file: a space after every comma, including the header.
SAMPLE = """\
SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER
TCS, EQ, 22-Oct-2026, 2529.00, 2520.00, 2533.00, 2479.00, 2506.90, 2506.90, 2504.36, 4174671, 104548.87, 213803, 1789271, 42.86
20MICRONS, EQ, 22-Oct-2026, 180.33, 180.33, 183.30, 176.42, 177.50, 178.03, 179.39, 64127, 115.04, 2881, 29072, 45.34
ABCBE, BE, 22-Oct-2026, 10.00, 10.00, 10.50, 9.80, 10.20, 10.20, 10.10, 1000, 1.01, 5, 800, 80.00
XYZSM, SM, 22-Oct-2026, 50.00, 50.00, 51.00, 49.00, 50.50, 50.50, 50.20, 500, 0.25, 2, 100, 20.00
NOTRADE, EQ, 22-Oct-2026, 5.00, -, -, -, -, 5.00, -, 0, 0.00, 0, -, -
"""


def test_keeps_only_eq_and_be_rows():
    rows = parse_delivery(SAMPLE)
    assert [r["symbol"] for r in rows] == ["TCS", "20MICRONS", "ABCBE", "NOTRADE"]


def test_parses_quantity_percentage_and_date():
    tcs = parse_delivery(SAMPLE)[0]
    assert tcs == {"symbol": "TCS", "trade_date": date(2026, 10, 22), "deliv_qty": 1789271, "deliv_pct": 42.86}


def test_dash_cells_become_none():
    notrade = parse_delivery(SAMPLE)[-1]
    assert notrade["deliv_qty"] is None and notrade["deliv_pct"] is None


def test_byte_order_mark_and_padding_are_ignored():
    rows = parse_delivery("﻿" + SAMPLE)
    assert rows[0]["symbol"] == "TCS" and rows[0]["deliv_pct"] == 42.86


def test_header_only_file_gives_no_rows():
    assert parse_delivery(SAMPLE.splitlines()[0] + "\n") == []


def test_delivery_url_uses_ddmmyyyy():
    assert delivery_url(date(2026, 10, 22)).endswith("/products/content/sec_bhavdata_full_22102026.csv")
