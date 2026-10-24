from datetime import date, timedelta

from app.services import compare as svc


def series(closes, start=date(2024, 1, 1)):
    return [{"trade_date": start + timedelta(days=i), "close": c} for i, c in enumerate(closes)]


def test_drawdown_peak_trough_and_recovery():
    dd = svc.drawdown(series([100, 120, 90, 60, 100, 130]))
    assert dd["pct"] == -50.0
    assert dd["peak"] == "2024-01-02" and dd["trough"] == "2024-01-04"
    assert dd["recovered"] == "2024-01-06"
    assert dd["current_pct"] == 0.0


def test_drawdown_not_recovered():
    dd = svc.drawdown(series([100, 80, 90]))
    assert dd["pct"] == -20.0 and dd["recovered"] is None and dd["current_pct"] == -10.0


def test_beta_and_correlation_of_scaled_series():
    idx = series([100 * (1 + 0.01 * ((-1) ** i) * (i % 7)) for i in range(60)])
    rets_idx = svc.daily_returns(idx)
    doubled = {d: 2 * r for d, r in rets_idx.items()}
    assert svc.beta(doubled, rets_idx) == 2.0
    assert svc.correlation(doubled, rets_idx) == 1.0
    assert svc.correlation({d: -r for d, r in rets_idx.items()}, rets_idx) == -1.0


def test_too_little_data_gives_none():
    short = svc.daily_returns(series([1, 2, 3]))
    assert svc.beta(short, short) is None and svc.correlation(short, short) is None


def test_window_and_weekly_rebase():
    rows = series([100 + i for i in range(800)])
    w = svc.window(rows, 1)
    assert (w[-1]["trade_date"] - w[0]["trade_date"]).days <= 366
    pts = svc.rebased(w, weekly=True)
    assert pts[0]["value"] == 100.0 and pts[-1]["time"] == w[-1]["trade_date"].isoformat()
    assert len(pts) < len(w) / 5


def test_stats_total_return_and_cagr():
    rows = series([100 * 1.0004 ** i for i in range(800)])
    s = svc.stats(rows, {}, 2)
    assert s["full_window"] and s["cagr"] is not None and s["total_return"] > 0 and s["beta"] is None
