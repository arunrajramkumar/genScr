import statistics
from datetime import date, timedelta

import pytest

from app.services.valuation import WINDOW_DAYS, _events, _filings, pb_at, trailing_eps, valuation_history


def daily(start, end, price=100.0, weekdays_only=False):
    out = []
    d = start
    while d <= end:
        if not weekdays_only or d.weekday() < 5:
            out.append({"trade_date": d, "open": price, "close": price, "prev_close": None})
        d += timedelta(days=1)
    return out


def fund(period_end, ptype, eps=None, equity=None, shares=None):
    return {"period_end": period_end, "period_type": ptype, "eps": eps, "total_equity": equity, "shares_outstanding": shares}


def annual_eps(eps=10.0, years=(2024, 2025, 2026)):
    return [fund(date(y, 3, 31), "FY", eps=eps) for y in years]


# --- look-ahead and publication lag -------------------------------------------------------------

def test_quarter_is_not_used_before_it_is_public():
    filings = _filings([
        fund(date(2025, 3, 31), "FY", eps=40),
        fund(date(2025, 3, 31), "Q", eps=10),  # Q4: public 60 days after period end
        fund(date(2025, 6, 30), "Q", eps=12),  # public 14 Aug 2025
        fund(date(2025, 9, 30), "Q", eps=12),  # public 14 Nov 2025
        fund(date(2025, 12, 31), "Q", eps=12),  # public 14 Feb 2026
    ])
    assert [f["public"] for f in filings if f["period_type"] == "Q"][-1] == date(2025, 5, 30)
    # Before Dec 2025 is public only three quarters are known, so the FY figure is the trailing one.
    assert trailing_eps(filings, [], date(2026, 2, 13)) == 40
    assert trailing_eps(filings, [], date(2026, 2, 14)) == 46  # 10 + 12 + 12 + 12


def test_nothing_is_used_before_the_first_filing_is_public():
    filings = _filings([fund(date(2025, 3, 31), "FY", eps=40)])
    assert trailing_eps(filings, [], date(2025, 5, 29)) is None
    assert trailing_eps(filings, [], date(2025, 5, 30)) == 40


def test_valuation_pe_has_no_look_ahead():
    # Only FY figures; the first P/E week must fall after the FY is public (30 May 2024), not at period end.
    out = valuation_history(daily(date(2024, 1, 1), date(2025, 12, 31)), annual_eps())
    assert out["pe"]["since"] >= "2024-05-30"


# --- missing quarters and the consecutive-quarter rule ---------------------------------------

def test_missing_quarter_falls_back_to_latest_fy():
    filings = _filings([
        fund(date(2025, 3, 31), "FY", eps=40),
        fund(date(2025, 3, 31), "Q", eps=10),
        fund(date(2025, 6, 30), "Q", eps=12),
        fund(date(2025, 12, 31), "Q", eps=12),  # Sep 2025 missing
        fund(date(2026, 3, 31), "Q", eps=12),
        fund(date(2026, 3, 31), "FY", eps=48),
    ])
    # The four newest quarters are not consecutive, so the latest FY is used.
    assert trailing_eps(filings, [], date(2026, 8, 1)) == 48


def test_quarters_older_than_latest_fy_are_not_used():
    filings = _filings([
        fund(date(2025, 3, 31), "Q", eps=10),
        fund(date(2025, 6, 30), "Q", eps=10),
        fund(date(2025, 9, 30), "Q", eps=10),
        fund(date(2025, 12, 31), "Q", eps=10),
        fund(date(2026, 3, 31), "FY", eps=48),  # its Q4 row is missing, so the FY is newer than the quarters
    ])
    assert trailing_eps(filings, [], date(2026, 6, 1)) == 48


def test_four_consecutive_quarters_are_summed():
    filings = _filings([
        fund(date(2025, 3, 31), "Q", eps=10),
        fund(date(2025, 6, 30), "Q", eps=11),
        fund(date(2025, 9, 30), "Q", eps=12),
        fund(date(2025, 12, 31), "Q", eps=13),
    ])
    assert trailing_eps(filings, [], date(2026, 3, 1)) == 46


def test_stale_filing_is_not_trailing():
    filings = _filings([fund(date(2022, 3, 31), "FY", eps=30)])
    assert trailing_eps(filings, [], date(2024, 1, 1)) is None


# --- losses -------------------------------------------------------------------------------------

def test_loss_making_weeks_are_counted_but_not_plotted():
    # Loss for FY Mar 2024 (public from 30 May 2024), then profit: P/E only from 30 May 2025 on.
    fundamentals = [fund(date(2024, 3, 31), "FY", eps=-5), fund(date(2025, 3, 31), "FY", eps=10),
                    fund(date(2026, 3, 31), "FY", eps=12)]
    out = valuation_history(daily(date(2023, 4, 1), date(2026, 8, 31)), fundamentals)
    pe = out["pe"]
    # Daily rows, so each week is sampled on its Sunday. The loss filing is public and not stale from
    # 30 May 2024 through 5 May 2025 (stale after period end + 400 days), so those Sundays are the loss weeks.
    sundays = [d for d in (date(2024, 5, 30) + timedelta(days=i) for i in range(341)) if d.weekday() == 6]
    assert pe["loss_weeks"] == len(sundays)
    assert pe["since"] >= "2025-05-30"
    assert pe["min"] == pytest.approx(8.33) and pe["max"] == pytest.approx(10.0)
    assert all(p["value"] > 0 for p in pe["points"])


def test_latest_loss_week_has_no_current_pe():
    fundamentals = [fund(date(2024, 3, 31), "FY", eps=10), fund(date(2025, 3, 31), "FY", eps=10),
                    fund(date(2026, 3, 31), "FY", eps=-1)]
    out = valuation_history(daily(date(2024, 6, 1), date(2026, 7, 31)), fundamentals)
    assert out["pe"]["current"] is None
    assert out["pe"]["percentile"] is None
    assert out["pe"]["loss_weeks"] >= 1


def test_all_loss_making_has_no_pe_points_but_reports_the_losses():
    fundamentals = [fund(date(2024, 3, 31), "FY", eps=-5), fund(date(2025, 3, 31), "FY", eps=-3),
                    fund(date(2026, 3, 31), "FY", eps=-2)]
    out = valuation_history(daily(date(2024, 1, 1), date(2026, 7, 31)), fundamentals)
    assert out["pe"]["points"] == [] and out["pe"]["current"] is None
    assert out["pe"]["loss_weeks"] > 100


def test_short_loss_spell_has_no_pe_summary():
    # Only a few weeks of losses and no profit weeks: too little to say anything about P/E.
    fundamentals = [fund(date(2025, 3, 31), "FY", eps=-3)]
    out = valuation_history(daily(date(2025, 1, 1), date(2025, 9, 30)), fundamentals)
    assert out["pe"] is None


# --- splits and bonuses in the middle of the series ----------------------------------------------

SPLIT = [{"ex_date": date(2025, 1, 15), "kind": "split", "ratio_new": None, "ratio_held": None, "old_fv": 10, "new_fv": 5}]


def _split_prices():
    rows = daily(date(2024, 4, 1), date(2026, 3, 31))
    for r in rows:
        r["close"] = r["open"] = 1000.0 if r["trade_date"] < date(2025, 1, 15) else 500.0
    return rows


def test_split_events_are_the_adjust_factors():
    assert _events(_split_prices(), SPLIT) == [(date(2025, 1, 15), 0.5)]
    bonus = [{"ex_date": date(2025, 1, 15), "kind": "bonus", "ratio_new": 1, "ratio_held": 1}]
    assert _events(_split_prices(), bonus) == [(date(2025, 1, 15), 0.5)]


def test_split_keeps_pe_continuous():
    # Pre-split EPS 100 at price 1000 is P/E 10. After a 1:2 split the price is 500; the FY Mar24 EPS (published
    # before the split) is restated to 50, and the FY Mar25 EPS (published after) is already 50. P/E stays 10.
    fundamentals = [fund(date(2024, 3, 31), "FY", eps=100, equity=50000, shares=1_000_000_000),
                    fund(date(2025, 3, 31), "FY", eps=50, equity=50000, shares=2_000_000_000),
                    fund(date(2026, 3, 31), "FY", eps=50, equity=50000, shares=2_000_000_000)]
    out = valuation_history(_split_prices(), fundamentals, SPLIT)
    pe, pb = out["pe"], out["pb"]
    assert pe["min"] == pe["max"] == pe["median"] == pytest.approx(10.0)
    # Market cap is price x shares: 1000 x 1e9 / 1e7 = 1e5 crore; 500 x 2e9 / 1e7 = 1e5 crore. P/B stays 2.
    assert pb["min"] == pb["max"] == pytest.approx(2.0)


def test_without_the_split_action_the_eps_is_not_restated():
    # Guard for the test above: a non-split action disables the price-gap heuristic, so the pre-split EPS is
    # not restated and P/E halves right after the split (500 / 100 = 5).
    fundamentals = [fund(date(2024, 3, 31), "FY", eps=100), fund(date(2025, 3, 31), "FY", eps=50),
                    fund(date(2026, 3, 31), "FY", eps=50)]
    dividend = [{"ex_date": date(2024, 7, 1), "kind": "dividend", "amount": 1}]
    out = valuation_history(_split_prices(), fundamentals, dividend)
    assert out["pe"]["min"] == pytest.approx(5.0)


# --- P/B ----------------------------------------------------------------------------------------

def test_pb_uses_market_cap_over_latest_public_equity():
    filings = _filings([fund(date(2025, 3, 31), "FY", equity=50000, shares=1_000_000_000)])
    # 100 x 1e9 / 1e7 = 1e4 crore market cap over 5e4 crore equity.
    assert pb_at(filings, [], date(2025, 5, 30), 100.0) == pytest.approx(0.2)
    assert pb_at(filings, [], date(2025, 5, 29), 100.0) is None  # not public yet


def test_pb_skips_negative_or_missing_equity():
    neg = _filings([fund(date(2025, 3, 31), "FY", equity=-5, shares=1_000_000_000)])
    assert pb_at(neg, [], date(2025, 7, 1), 100.0) is None
    no_shares = _filings([fund(date(2025, 3, 31), "FY", equity=50, shares=None)])
    assert pb_at(no_shares, [], date(2025, 7, 1), 100.0) is None


def test_book_value_is_not_used_before_it_is_public():
    fundamentals = [fund(date(2024, 3, 31), "FY", eps=10, equity=50000, shares=1_000_000_000),
                    fund(date(2025, 3, 31), "FY", eps=10, equity=50000, shares=1_000_000_000),
                    fund(date(2026, 3, 31), "FY", eps=10, equity=50000, shares=1_000_000_000)]
    out = valuation_history(daily(date(2024, 1, 1), date(2026, 7, 31)), fundamentals)
    assert out["pb"]["since"] >= "2024-05-30"


# --- weekly sampling, window and statistics -----------------------------------------------------

def test_weekly_points_fall_on_last_trading_day():
    out = valuation_history(daily(date(2024, 1, 1), date(2026, 7, 31), weekdays_only=True), annual_eps())
    times = [date.fromisoformat(p["time"]) for p in out["pe"]["points"]]
    assert all(t.weekday() == 4 for t in times)  # rows run Monday to Friday, so each week ends on a Friday
    assert out["pe"]["points"][-1]["time"] == out["as_of"]


def test_summary_statistics_and_percentile():
    # EPS fixed at 10 and the price rises by one rupee a day, so P/E rises steadily.
    rows = [{"trade_date": date(2024, 6, 1) + timedelta(days=i), "close": 100.0 + i} for i in range(400)]
    pe = valuation_history(rows, annual_eps())["pe"]
    values = [p["value"] for p in pe["points"]]
    assert pe["current"] == values[-1] == pe["max"]
    assert pe["min"] == values[0]
    assert pe["median"] == round(statistics.median(values), 2)
    assert pe["percentile"] == round(100 * (len(values) - 1) / len(values))
    assert pe["years"] == pytest.approx(1.1, abs=0.1)
    assert all(round(v, 2) == v for v in values)


def test_series_is_limited_to_ten_years():
    rows = daily(date(2010, 1, 1), date(2026, 6, 30), weekdays_only=True)
    out = valuation_history(rows, annual_eps(years=range(2009, 2027)))
    as_of = date.fromisoformat(out["as_of"])
    assert out["pe"]["points"][0]["time"] >= (as_of - timedelta(days=WINDOW_DAYS)).isoformat()
    assert out["pe"]["years"] <= 10.05


def test_short_history_has_no_series():
    out = valuation_history(daily(date(2025, 1, 1), date(2025, 3, 31)), [fund(date(2024, 3, 31), "FY", eps=10)])
    assert out["pe"] is None and out["pb"] is None


def test_no_prices_returns_none():
    assert valuation_history([], annual_eps()) is None
