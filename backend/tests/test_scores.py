import pytest

from app.services.scores import altman_z, fundamental_ratios, piotroski_f

PREV = {
    "revenue": 1000, "operating_profit": 150, "pbt": 110, "interest": 10, "net_profit": 80,
    "total_assets": 1200, "total_equity": 600, "reserves": 500, "total_debt": 300,
    "current_assets": 500, "current_liabilities": 400, "cfo": 90, "shares_outstanding": 10_00_00_000,
}
CUR = {
    "revenue": 1200, "operating_profit": 200, "pbt": 160, "interest": 8, "net_profit": 120,
    "total_assets": 1300, "total_equity": 700, "reserves": 600, "total_debt": 250,
    "current_assets": 600, "current_liabilities": 400, "cfo": 150, "shares_outstanding": 10_00_00_000,
}


def test_piotroski_all_improving_scores_9():
    assert piotroski_f(CUR, PREV) == 9


def test_piotroski_needs_prior_year():
    assert piotroski_f(CUR, None) is None


def test_altman_z():
    z = altman_z(CUR)
    expected = 6.56 * 200 / 1300 + 3.26 * 600 / 1300 + 6.72 * 168 / 1300 + 1.05 * 700 / 600
    assert z == pytest.approx(expected)


def test_fundamental_ratios():
    r = fundamental_ratios(CUR, PREV, close=240.0)
    assert r["market_cap"] == pytest.approx(2400)  # 240 * 10 Cr shares = ₹2,400 Cr
    assert r["pe"] == pytest.approx(20)
    assert r["roe"] == pytest.approx(120 / 650 * 100)
    assert r["revenue_growth_yoy"] == pytest.approx(20)
    assert r["profit_growth_yoy"] == pytest.approx(50)
    assert r["debt_to_equity"] == pytest.approx(250 / 700)


def test_dividend_yield():
    r = fundamental_ratios({**CUR, "dividends_paid": 48.0}, PREV, close=240.0)
    assert r["dividend_yield"] == pytest.approx(2.0)  # ₹48 Cr / ₹2,400 Cr
    assert fundamental_ratios(CUR, PREV, close=240.0)["dividend_yield"] is None


def test_negative_earnings_have_no_pe():
    r = fundamental_ratios({**CUR, "net_profit": -5}, PREV, close=240.0)
    assert r["pe"] is None
    assert r["profit_growth_yoy"] is not None


def test_no_fundamentals():
    assert all(v is None for v in fundamental_ratios(None, None, 100).values())
