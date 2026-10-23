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


def test_no_corporate_action_is_noop():
    rows = [{"close": 100.0, "prev_close": 99.0}, {"close": 101.0, "prev_close": 100.0}]
    assert adjust(rows) == rows
