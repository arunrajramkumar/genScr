from datetime import date, timedelta

import pytest

from app.ingest.indices import parse_closes, parse_constituents
from app.ingest.symbol_changes import parse as parse_changes
from app.services.indices import category, percentile_of_latest, rebased, slugify, summarize


def test_parse_closes():
    text = ("Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,Closing Index Value,Points Change,"
            "Change(%),Volume,Turnover (Rs. Cr.),P/E,P/B,Div Yield\n"
            "Nifty 50,23-10-2026,22742.2,22787.25,22372,22600.0,-87.65,-.39,364190826,29859.76,19.05,2.78,1.52\n"
            "India VIX,23-10-2026,14,15,13,14.5,0.1,0.7,-,-,-,-,-\n")
    rows = parse_closes(text)
    assert rows[0]["index_name"] == "Nifty 50" and rows[0]["trade_date"] == date(2026, 10, 23)
    assert rows[0]["close"] == 22600.0 and rows[0]["pe"] == 19.05 and rows[0]["change_pct"] == -0.39
    assert rows[1]["pe"] is None


def test_parse_constituents_and_symbol_changes():
    assert parse_constituents("Company Name,Industry,Symbol,Series,ISIN Code\nTCS Ltd,IT,TCS,EQ,INE467B01029\n") == ["TCS"]
    changes = parse_changes("NAME OF THE COMPANY,OLD SYMBOL,NEW SYMBOL,EFFECTIVE DATE\nETERNAL LIMITED,ZOMATO,ETERNAL,09-APR-2025\n")
    assert changes == [{"old_symbol": "ZOMATO", "new_symbol": "ETERNAL", "effective_date": date(2025, 4, 9)}]


def test_slug_and_category():
    assert slugify("Nifty Oil & Gas") == "nifty-oil-gas"
    assert category("Nifty 50") == "Broad market"
    assert category("Nifty Bank") == "Sector & theme"
    assert category("Nifty 10 yr Benchmark G-Sec") == "Bonds & rates"
    assert category("Nifty Alpha 50") == "Strategy & factor"
    assert category("India VIX") == "Volatility"


def _rows(n=2000, start=date(2018, 1, 1)):
    return [{"trade_date": start + timedelta(days=i), "close": 100 * (1.0003 ** i), "change_pct": 0.03,
             "pe": 15 + (i % 100) / 10, "pb": 3, "div_yield": 1.2} for i in range(n)]


def test_summarize_returns_and_percentile():
    s = summarize("Nifty 50", _rows())
    assert s["slug"] == "nifty-50" and s["category"] == "Broad market"
    assert s["return_1y"] == pytest.approx((1.0003 ** 365 - 1) * 100, abs=0.2)
    assert s["cagr_5y"] is not None and s["pe_percentile"] is not None
    assert percentile_of_latest([1, 2, 3]) is None  # too little history


def test_rebased_starts_at_100():
    pts = rebased(_rows(), date(2020, 1, 1))
    assert pts[0]["value"] == 100.0 and len(pts) < 400


def test_returns_skip_bases_across_data_holes():
    start = date(2016, 1, 1)
    rows = [{"trade_date": start + timedelta(days=i), "close": 100.0 + i} for i in range(900)]
    rows += [{"trade_date": date(2026, 1, 1) + timedelta(days=i), "close": 200.0} for i in range(200)]
    s = summarize("Nifty 50", rows)
    assert s["cagr_3y"] is None and s["cagr_5y"] is None  # 2021/2023 fall in the hole
    assert s["return_1m"] == 0.0
