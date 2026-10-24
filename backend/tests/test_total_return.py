from datetime import date, timedelta

import pytest

from app.services.total_return import total_return


def prices(closes, start=date(2020, 1, 1)):
    return [{"trade_date": start + timedelta(days=i), "close": c} for i, c in enumerate(closes)]


def test_price_only_no_actions():
    r = total_return(prices([100, 110, 120]), [], date(2020, 1, 1), amount=10_000)
    assert r["initial_shares"] == 100
    assert r["price_only"]["total_value"] == 12_000
    assert r["with_dividends"]["total_value"] == 12_000
    assert r["dividends_received"] == 0


def test_bonus_doubles_shares_and_keeps_value():
    # 1:1 bonus: price halves, shares double -> value unchanged
    p = prices([100, 100, 50, 55])
    acts = [{"ex_date": date(2020, 1, 3), "kind": "bonus", "ratio_new": 1, "ratio_held": 1}]
    r = total_return(p, acts, date(2020, 1, 1))
    assert r["price_only"]["shares"] == 200
    assert r["bonus_split_shares"] == 100
    assert r["price_only"]["total_value"] == pytest.approx(11_000)
    assert r["events"][0]["kind"] == "bonus" and r["events"][0]["shares_added"] == 100


def test_split_multiplies_shares():
    p = prices([1000, 1000, 100])
    acts = [{"ex_date": date(2020, 1, 3), "kind": "split", "old_fv": 10, "new_fv": 1}]
    r = total_return(p, acts, date(2020, 1, 1))
    assert r["price_only"]["shares"] == 100  # 10 shares x 10
    assert r["price_only"]["total_value"] == pytest.approx(10_000)


def test_dividends_cash_vs_reinvested():
    p = prices([100, 100, 90, 100])
    acts = [{"ex_date": date(2020, 1, 3), "kind": "dividend", "amount": 10}]
    r = total_return(p, acts, date(2020, 1, 1))
    assert r["dividends_received"] == 1000  # 100 shares x Rs 10
    assert r["with_dividends"]["total_value"] == pytest.approx(11_000)  # 100 x 100 + 1000 cash
    # reinvested at 90: +11.11 shares -> 111.11 x 100
    assert r["reinvested"]["shares"] == pytest.approx(111.1111, rel=1e-4)
    assert r["reinvested"]["total_value"] == pytest.approx(11_111.11, rel=1e-4)
    assert r["price_only"]["total_value"] == pytest.approx(10_000)


def test_dividend_paid_on_pre_bonus_holding_same_day():
    p = prices([100, 100, 50])
    acts = [
        {"ex_date": date(2020, 1, 3), "kind": "bonus", "ratio_new": 1, "ratio_held": 1},
        {"ex_date": date(2020, 1, 3), "kind": "dividend", "amount": 5},
    ]
    r = total_return(p, acts, date(2020, 1, 1))
    assert r["dividends_received"] == 500  # 100 pre-bonus shares x Rs 5, not 200 x 5
    assert r["with_dividends"]["shares"] == 200


def test_actions_before_start_are_ignored_and_demerger_flagged():
    p = prices([100, 100, 100], start=date(2020, 1, 10))
    acts = [{"ex_date": date(2020, 1, 1), "kind": "dividend", "amount": 50},
            {"ex_date": date(2020, 1, 11), "kind": "demerger"}]
    r = total_return(p, acts, date(2020, 1, 10))
    assert r["dividends_received"] == 0
    assert r["caveats"] and "2020-01-11" in r["caveats"][0]


def test_not_enough_data():
    assert total_return(prices([100]), [], date(2020, 1, 1)) is None


def test_series_is_monthly():
    p = prices([100 + i for i in range(70)])  # ~2.3 months of daily points
    r = total_return(p, [], date(2020, 1, 1))
    assert len(r["series"]) == 3 and set(r["series"][0]) == {"time", "price", "cash", "reinvest"}
