from datetime import date, timedelta

from app.ingest.compute_metrics import price_metrics


def _rows(days: list[date], highs: list[float]) -> list[dict]:
    return [{"trade_date": d, "close": 10.0, "prev_close": 10.0, "high": h, "low": 9.0, "volume": 100,
             "turnover": 1e7, "deliv_pct": None} for d, h in zip(days, highs, strict=True)]


def test_52_week_range_is_by_date_for_rarely_traded_stocks():
    end = date(2026, 10, 23)
    days = [end - timedelta(days=700), end - timedelta(days=200), end]  # 3 trades in ~2 years
    m = price_metrics(_rows(days, [50.0, 12.0, 11.0]))
    assert m["high_52w"] == 12.0  # the high from ~2 years ago is outside the 52 weeks


def test_average_volume_ignores_missing_volumes():
    end = date(2026, 10, 23)
    rows = _rows([end - timedelta(days=1), end], [11.0, 11.0])
    rows[0]["volume"] = None
    assert price_metrics(rows)["avg_volume_20d"] == 100
