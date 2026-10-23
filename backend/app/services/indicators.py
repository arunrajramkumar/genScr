"""Technical indicators on plain lists of floats (oldest first)."""

from itertools import pairwise


def sma(values: list[float], n: int) -> float | None:
    if n <= 0 or len(values) < n:
        return None
    return sum(values[-n:]) / n


def rsi(closes: list[float], n: int = 14) -> float | None:
    """Wilder's RSI."""
    if len(closes) < n + 1:
        return None
    diffs = [b - a for a, b in pairwise(closes)]
    avg_gain = sum(d for d in diffs[:n] if d > 0) / n
    avg_loss = sum(-d for d in diffs[:n] if d < 0) / n
    for d in diffs[n:]:
        avg_gain = (avg_gain * (n - 1) + max(d, 0)) / n
        avg_loss = (avg_loss * (n - 1) + max(-d, 0)) / n
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def pct_return(closes: list[float], lookback: int) -> float | None:
    if len(closes) <= lookback:
        return None
    base = closes[-1 - lookback]
    if not base:
        return None
    return (closes[-1] / base - 1) * 100
