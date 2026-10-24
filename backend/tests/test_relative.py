from datetime import date, timedelta

from app.services.relative import compare_to_index


def _days(n, start=date(2020, 1, 1)):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _series(days, f):
    return [{"trade_date": d, "close": f(i)} for i, d in enumerate(days)]


def test_identical_series_have_beta_one_and_no_difference():
    days = _days(800)
    s = _series(days, lambda i: 100 * (1.001 ** i) * (1 + 0.02 * ((i % 7) - 3) / 3))
    r = compare_to_index(s, s, 3)
    assert r["stats"]["beta"] == 1.0 and r["stats"]["correlation"] == 1.0
    assert all(x["difference"] == 0 for x in r["returns"])
    assert r["series"][0]["stock"] == r["series"][0]["index"] == 100
    assert all(p["relative"] == 100 for p in r["series"])


def test_double_moves_give_beta_two_and_wider_drawdown():
    days = _days(800)
    idx = _series(days, lambda i: 1000 * (1 + 0.05 * ((i // 10) % 2)))  # steps up and down 5%
    stock = _series(days, lambda i: 100 * (1 + 0.10 * ((i // 10) % 2)))
    st = compare_to_index(stock, idx, 3)["stats"]
    assert 1.8 < st["beta"] < 2.2
    assert st["max_drawdown_stock"] < st["max_drawdown_index"] < 0


def test_only_common_trading_days_are_used_and_short_overlap_returns_none():
    days = _days(400)
    idx = _series(days, lambda i: 1000 + i)
    stock = _series(days[-20:], lambda i: 50 + i)  # listed recently
    assert compare_to_index(stock, idx, 5) is None
    r = compare_to_index(_series(days[100:], lambda i: 50 + i), idx, 5)
    assert r["start"] == days[100].isoformat()


def test_returns_skip_periods_longer_than_history_and_calendar_marks_partial_years():
    days = _days(300, date(2024, 3, 1))
    s = _series(days, lambda i: 100 + i)
    r = compare_to_index(s, _series(days, lambda i: 1000.0), 5)
    assert [x["period"] for x in r["returns"]] == ["1M", "6M", "1Y"]
    assert r["calendar"][0]["partial"] and r["calendar"][0]["year"] == 2024
    assert r["returns"][-1]["index"] == 0.0
