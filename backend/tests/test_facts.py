from datetime import date, timedelta

from app.services.facts import build_facts, fy_label, inr


def test_inr_grouping():
    assert inr(1234567) == "12,34,567"
    assert inr(999) == "999"
    assert inr(1345.67, 1) == "1,345.7"


def test_fy_label():
    assert fy_label(date(2026, 3, 31)) == "FY26"
    assert fy_label(date(2025, 12, 31)) == "FY26"


def _prices(n=600, start=date(2020, 1, 1)):
    rows, close = [], 100.0
    for i in range(n):
        prev = close
        close = prev * (1.002 if i % 3 else 0.999)
        if i == 300:
            close = prev * 1.12  # a +12% day
        if 400 <= i < 410:
            close = prev * 1.01  # 10-day streak
        rows.append({"trade_date": start + timedelta(days=i), "open": prev, "high": close, "low": prev,
                     "close": close, "prev_close": prev, "volume": 1000})
    return rows


def test_build_facts_from_filings_prices_and_rank():
    stock = {"symbol": "X", "sector": "IT", "market_cap": 10000.0, "listing_date": date(2004, 8, 25)}
    fy = [
        {"period_end": date(2026, 3, 31), "net_profit": 3650.0, "revenue": 30000.0, "total_debt": 0.0,
         "total_assets": 50000.0, "cash": 2000.0, "source": "consolidated xbrl"},
        {"period_end": date(2024, 3, 31), "net_profit": 2000.0, "revenue": 15000.0},
    ]
    rank = {"rank": 3, "total": 400, "sector_rank": 1, "sector_total": 40}
    facts = {f["id"]: f for f in build_facts(stock, _prices(), fy, rank, today=date(2026, 10, 23))}

    assert facts["profit_per_day"]["text"].startswith("Earned ₹10.0 Cr of profit every single day in FY26")
    assert "FY26" in facts["profit_per_day"]["source"]
    assert "2.0x" in facts["revenue_multiple"]["text"]
    assert facts["debt_free"]["title"] == "Debt-free"
    assert "20% of its entire market value" in facts["cash_pile"]["text"]
    assert "#3 most valuable of the 400" in facts["mcap_rank"]["text"]
    assert "most valuable company in IT" in facts["sector_leader"]["text"]
    assert "+12.0%" in facts["best_day"]["text"]
    assert facts["win_streak"]["text"].startswith("Rose 11 sessions in a row")
    assert "22 years" in facts["listed_since"]["text"]
    assert all(f["source"] for f in facts.values())


def test_no_data_no_facts():
    assert build_facts({"symbol": "X"}, [], [], None) == []


def test_small_universe_skips_rank_and_loss_is_reported():
    fy = [{"period_end": date(2026, 3, 31), "net_profit": -365.0}]
    facts = {f["id"] for f in build_facts({"symbol": "X"}, [], fy, {"rank": 1, "total": 10})}
    assert facts == {"loss_per_day"}
