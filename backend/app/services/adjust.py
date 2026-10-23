"""Back-adjust prices for splits / bonuses.

On an ex-date NSE publishes `prev_close` already adjusted for the corporate action, so
prev_close[t] / close[t-1] gives the adjustment factor (e.g. 0.5 for a 1:1 bonus).
"""

THRESHOLD = 0.005  # ignore tiny mismatches from rounding / ordinary dividends

PRICE_KEYS = ("open", "high", "low", "close")


def adjust(rows: list[dict]) -> list[dict]:
    """Return copies of `rows` (oldest first, floats) with OHLC back-adjusted and volume scaled."""
    out = [dict(r) for r in rows]
    factor = 1.0
    for i in range(len(out) - 1, 0, -1):
        prev_close, last_close = rows[i].get("prev_close"), rows[i - 1].get("close")
        if prev_close and last_close:
            ratio = prev_close / last_close
            if abs(ratio - 1) > THRESHOLD:
                factor *= ratio
        if factor != 1.0:
            r = out[i - 1]
            for k in PRICE_KEYS:
                if r.get(k) is not None:
                    r[k] = r[k] * factor
            if r.get("volume") is not None:
                r["volume"] = int(r["volume"] / factor)
    return out
