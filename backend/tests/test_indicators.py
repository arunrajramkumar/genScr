import pytest

from app.services.indicators import pct_return, rsi, sma


def test_sma():
    assert sma([1, 2, 3, 4], 2) == 3.5
    assert sma([1, 2], 3) is None


def test_rsi_bounds():
    assert rsi(list(range(1, 30))) == 100.0
    assert rsi(list(range(30, 1, -1))) == pytest.approx(0.0)
    assert rsi([1, 2]) is None
    value = rsi([44, 44.3, 44.1, 43.6, 44.3, 44.8, 45.1, 45.4, 45.8, 46.1, 45.9, 46.3, 46.0, 46.4, 46.2, 45.6])
    assert 0 < value < 100


def test_pct_return():
    assert pct_return([100, 110, 121], 2) == pytest.approx(21.0)
    assert pct_return([100], 1) is None


def test_cagr_and_volatility():
    from app.services.indicators import cagr, volatility

    closes = [100 * (1.1 ** (i / 248)) for i in range(3 * 248 + 1)]  # 10% a year
    assert cagr(closes, 3) == pytest.approx(10.0, abs=0.01)
    assert cagr(closes, 5) is None
    flat = [100.0] * 300
    assert volatility(flat) == 0
    assert volatility([100.0] * 30) is None
