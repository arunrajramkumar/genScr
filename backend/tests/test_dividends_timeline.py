from datetime import date, timedelta

import pytest

from app.services.adjust import adjust
from app.services.compliance import is_compliant
from app.services.dividends import dividend_history, fy_of, share_factor_after, ttm_dividend_yield
from app.services.timeline import build_timeline


def test_fy_of():
    assert fy_of(date(2025, 5, 15)) == 2026
    assert fy_of(date(2026, 2, 4)) == 2026
    assert fy_of(date(2026, 4, 1)) == 2027


def test_share_factor_after_bonus_and_split():
    acts = [{"ex_date": date(2020, 1, 1), "kind": "bonus", "ratio_new": 1, "ratio_held": 1},
            {"ex_date": date(2022, 1, 1), "kind": "split", "old_fv": 10, "new_fv": 2}]
    assert share_factor_after(date(2019, 6, 1), acts) == pytest.approx(0.5 * 0.2)
    assert share_factor_after(date(2021, 6, 1), acts) == pytest.approx(0.2)
    assert share_factor_after(date(2023, 6, 1), acts) == 1.0


def _prices(start=date(2018, 1, 1), days=3000, close=100.0):
    return [{"trade_date": start + timedelta(days=i), "close": close} for i in range(days)]


def test_dividend_history_years_streak_and_adjusted_amounts():
    acts = [
        {"ex_date": date(2019, 6, 1), "kind": "dividend", "amount": 10},   # FY20, before bonus
        {"ex_date": date(2020, 6, 1), "kind": "bonus", "ratio_new": 1, "ratio_held": 1},
        {"ex_date": date(2020, 7, 1), "kind": "dividend", "amount": 6},    # FY21
        {"ex_date": date(2021, 7, 1), "kind": "dividend", "amount": 7},    # FY22
        {"ex_date": date(2022, 2, 1), "kind": "dividend", "amount": 1},    # FY22 interim
        {"ex_date": date(2022, 7, 1), "kind": "dividend", "amount": 9},    # FY23
    ]
    h = dividend_history(acts, _prices(), today=date(2023, 10, 1))
    assert [y["fy"] for y in h["years"]] == [2020, 2021, 2022, 2023]
    assert h["payments"][0]["adjusted_amount"] == 5  # ₹10 before a 1:1 bonus = ₹5 in today's shares
    fy22 = next(y for y in h["years"] if y["fy"] == 2022)
    assert fy22["declared"] == 8 and fy22["payments"] == 2
    assert h["payments"][0]["yield_pct"] == 10  # ₹10 on a ₹100 price
    assert h["stats"]["paying_streak_years"] == 4  # FY20..FY23, current FY24 not complete
    assert h["stats"]["growth_streak_years"] == 3  # adjusted 5 -> 6 -> 8 -> 9: three increases
    assert h["stats"]["first_dividend"] == "2019-06-01"


def test_ttm_dividend_yield_uses_last_12_months_in_todays_shares():
    acts = [
        {"ex_date": date(2025, 8, 21), "kind": "dividend", "amount": 5.15},   # older than 12 months
        {"ex_date": date(2025, 11, 4), "kind": "dividend", "amount": 10.25},
        {"ex_date": date(2026, 2, 18), "kind": "dividend", "amount": 5.5},
        {"ex_date": date(2026, 7, 31), "kind": "dividend", "amount": 5.5},
        {"ex_date": date(2026, 9, 4), "kind": "dividend", "amount": 5.25},
    ]
    assert ttm_dividend_yield(acts, date(2026, 10, 23), 397.45) == pytest.approx(6.67, abs=0.01)  # Coal India
    bonus = [{"ex_date": date(2026, 1, 1), "kind": "dividend", "amount": 10},
             {"ex_date": date(2026, 6, 1), "kind": "bonus", "ratio_new": 1, "ratio_held": 1}]
    assert ttm_dividend_yield(bonus, date(2026, 10, 1), 50) == pytest.approx(10.0)  # ₹10 pre-bonus = ₹5 now
    assert ttm_dividend_yield([], date(2026, 10, 1), 50) == 0
    assert ttm_dividend_yield(acts, date(2026, 10, 23), None) is None


def test_dividend_history_empty():
    h = dividend_history([], _prices())
    assert h["payments"] == [] and h["stats"]["paying_streak_years"] == 0


def test_timeline_events_are_sorted_sourced_and_compliant():
    stock = {"symbol": "X", "name": "X Ltd", "listing_date": date(2004, 8, 25)}
    acts = [
        {"ex_date": date(2019, 6, 1), "kind": "dividend", "amount": 10},
        {"ex_date": date(2019, 11, 1), "kind": "dividend", "amount": 5},
        {"ex_date": date(2020, 6, 1), "kind": "bonus", "ratio_new": 1, "ratio_held": 1},
        {"ex_date": date(2021, 3, 1), "kind": "split", "old_fv": 10, "new_fv": 2},
        {"ex_date": date(2022, 1, 1), "kind": "buyback"},
        {"ex_date": date(2023, 1, 1), "kind": "demerger"},
    ]
    prices = [{"trade_date": date(2018, 1, 1) + timedelta(days=i), "close": 100 + (i % 400) - (200 if 600 < i < 700 else 0),
               "prev_close": None} for i in range(1500)]
    ev = build_timeline(stock, acts, prices)
    kinds = [e["kind"] for e in ev]
    assert kinds[0] == "listing"
    assert {"milestone", "dividend", "bonus", "split", "buyback", "demerger", "high"} <= set(kinds)
    assert [e["date"] for e in ev] == sorted(e["date"] for e in ev)
    fy20 = next(e for e in ev if e["kind"] == "dividend")
    assert "₹15.00 per share across 2 payments" in fy20["text"]
    assert all(e["source"] and is_compliant(e["title"]) and is_compliant(e["text"]) for e in ev)
    assert all("--" not in e["text"] and "-%" not in e["text"] for e in ev)


def test_recorded_actions_replace_gap_heuristic():
    rows = [{"trade_date": date(2020, 1, 1), "open": 100.0, "close": 100.0, "prev_close": 100.0},
            {"trade_date": date(2020, 1, 2), "open": 50.0, "close": 50.0, "prev_close": 100.0}]
    # Heuristic alone would see a 0.5 gap; a recorded 1:4 split overrides it with the true factor.
    assert adjust(rows)[0]["close"] == pytest.approx(50.0)
    split = [{"ex_date": date(2020, 1, 2), "kind": "split", "old_fv": 4, "new_fv": 1}]
    assert adjust(rows, split)[0]["close"] == pytest.approx(25.0)
    # With actions supplied (even unrelated), a gap that isn't a recorded action is a real price move.
    other = [{"ex_date": date(2020, 1, 2), "kind": "dividend", "amount": 1}]
    assert adjust(rows, other)[0]["close"] == pytest.approx(100.0)
