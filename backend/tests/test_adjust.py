import pytest

from app.services.adjust import adjust


def test_bonus_is_back_adjusted():
    rows = [
        {"close": 3000.0, "prev_close": 2990.0, "high": 3010.0, "volume": 100},
        {"close": 3100.0, "prev_close": 3000.0, "high": 3120.0, "volume": 100},
        # 1:1 bonus ex-date: NSE reports prev_close as 1550 (= 3100 / 2)
        {"close": 1560.0, "prev_close": 1550.0, "high": 1570.0, "volume": 200},
    ]
    out = adjust(rows)
    assert [r["close"] for r in out] == pytest.approx([1500.0, 1550.0, 1560.0])
    assert out[0]["high"] == pytest.approx(1505.0)
    assert out[0]["volume"] == 200
    assert rows[0]["close"] == 3000.0  # input untouched


def test_dividend_day_prev_close_adjustment_is_ignored():
    from datetime import date

    rows = [{"trade_date": date(2026, 1, 1), "close": 100.0, "prev_close": 100.0},
            {"trade_date": date(2026, 1, 2), "close": 95.0, "prev_close": 95.0}]  # NSE lowered prev_close for a ₹5 dividend
    acts = [{"ex_date": date(2026, 1, 2), "kind": "dividend", "amount": 5}]
    assert adjust(rows, acts)[0]["close"] == 100.0  # price-only: not scaled
    assert adjust(rows)[0]["close"] == pytest.approx(95.0)  # without action data it's treated as an adjustment


def test_no_corporate_action_is_noop():
    rows = [{"close": 100.0, "prev_close": 99.0}, {"close": 101.0, "prev_close": 100.0}]
    assert adjust(rows) == rows


def test_legacy_bonus_detected_from_gap():
    # Pre-2024 bhavcopy: prev_close NOT adjusted on the 1:1 bonus ex-date
    rows = [
        {"open": 3500.0, "close": 3520.0, "prev_close": 3480.0},
        {"open": 1765.0, "close": 1770.0, "prev_close": 3520.0},
    ]
    out = adjust(rows)
    assert out[0]["close"] == pytest.approx(1760.0)


def test_genuine_crash_not_treated_as_split():
    rows = [{"open": 100.0, "close": 100.0, "prev_close": 100.0}, {"open": 72.0, "close": 70.0, "prev_close": 100.0}]
    assert adjust(rows)[0]["close"] == 100.0
