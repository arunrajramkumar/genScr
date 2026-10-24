from datetime import date, timedelta

import pytest

from app.services.ranks import percentile_ranks
from app.services.risk import risk_profile


def series(values, start=date(2022, 1, 3)):
    return [{"trade_date": start + timedelta(days=i), "close": v} for i, v in enumerate(values)]


def test_drawdown_depth_dates_and_recovery():
    vals = [100] * 10 + [110, 90, 80, 95, 111] + [111 + i * 0.1 for i in range(60)]
    r = risk_profile(series(vals))
    worst = r["worst_drawdowns"][0]
    assert worst["depth_pct"] == pytest.approx((80 / 110 - 1) * 100, abs=0.01)
    assert worst["peak_date"] == (date(2022, 1, 3) + timedelta(days=10)).isoformat()
    assert worst["recovered_date"] == (date(2022, 1, 3) + timedelta(days=14)).isoformat()
    assert r["current_drawdown_pct"] == 0


def test_unrecovered_drawdown_and_current_drawdown():
    vals = [100 + i for i in range(60)] + [100] * 30  # peak 159 then flat at 100
    r = risk_profile(series(vals))
    assert r["worst_drawdowns"][0]["recovered_date"] is None
    assert r["current_drawdown_pct"] == pytest.approx((100 / 159 - 1) * 100, abs=0.01)


def test_calendar_and_seasonality():
    rows = []
    d = date(2020, 1, 1)
    price = 100.0
    while d <= date(2023, 6, 30):
        if d.day == 1:
            price *= 1.02 if d.month == 12 else 0.995  # Decembers up
        rows.append({"trade_date": d, "close": price})
        d += timedelta(days=1)
    r = risk_profile(rows)
    dec = next(s for s in r["seasonality"] if s["month"] == 12)
    assert dec["up"] == dec["years"] == 3
    years = [c["year"] for c in r["calendar_years"]]
    assert years == [2021, 2022, 2023] and r["calendar_years"][-1]["partial"] is True
    assert len(r["underwater"]) < len(rows) / 5  # weekly sampling


def test_not_enough_history():
    assert risk_profile(series([100] * 30)) is None


def test_percentile_ranks_direction_and_sector():
    rows = [{"symbol": f"S{i}", "sector": "IT", "roe": i * 5, "debt_to_equity": i / 10, "pe": 10 + i} for i in range(10)]
    rows += [{"symbol": "X", "sector": "Bank", "roe": 50, "debt_to_equity": 5, "pe": -3}]
    r = percentile_ranks("S9", rows)
    roe = next(m for m in r["metrics"] if m["field"] == "roe")
    assert roe["sector_percentile"] == 100 and roe["sector_rank"] == 1 and roe["sector_total"] == 10
    de = next(m for m in r["metrics"] if m["field"] == "debt_to_equity")
    assert de["sector_percentile"] == 0  # highest debt in sector -> behind everyone
    pe = next(m for m in r["metrics"] if m["field"] == "pe")
    assert pe["market_total"] == 10  # negative P/E excluded
    assert percentile_ranks("NOPE", rows)["metrics"] == []
