"""Back-adjust prices for splits / bonuses.

When corporate actions are supplied they are authoritative for bonuses and splits.
Otherwise (or on days without a recorded action) two signals are used, per trading day t:
1. Since the UDiFF format (Jul 2024) NSE publishes `prev_close` already adjusted on an ex-date,
   so prev_close[t] / close[t-1] is the adjustment factor (e.g. 0.5 for a 1:1 bonus).
2. Older bhavcopies don't adjust prev_close, so we also look for an overnight gap that
   matches a standard split/bonus ratio (1:1 bonus = 0.5, 1:10 split = 0.1, ...).
"""

THRESHOLD = 0.005  # ignore tiny prev_close mismatches from rounding / ordinary dividends

# Factors for common bonuses (a:b -> b/(a+b)) and splits (1:n -> 1/n).
STANDARD_FACTORS = (0.1, 0.2, 0.25, 1 / 3, 0.4, 0.5, 2 / 3, 0.75)
GAP_TOLERANCE = 0.02  # relative distance from a standard factor
MIN_GAP = 0.20  # only consider overnight drops of 20%+

PRICE_KEYS = ("open", "high", "low", "close")


def action_factors(rows: list[dict], actions: list[dict]) -> dict[int, float]:
    """{index t: factor} from recorded bonuses/splits, mapped to the first trading day on/after the ex-date."""
    out: dict[int, float] = {}
    dates = [r["trade_date"] for r in rows]
    for a in actions:
        if a["kind"] == "bonus" and a.get("ratio_held"):
            f = a["ratio_held"] / (a["ratio_held"] + a["ratio_new"])
        elif a["kind"] == "split" and a.get("old_fv") and a.get("new_fv"):
            f = a["new_fv"] / a["old_fv"]
        else:
            continue
        i = next((j for j, d in enumerate(dates) if d >= a["ex_date"]), None)
        if i:  # an action on the very first row has nothing earlier to adjust
            out[i] = out.get(i, 1.0) * f
    return out


def split_factors(rows: list[dict], actions: list[dict] | None = None) -> dict[int, float]:
    """{index t: factor} for days where a corporate action took effect (rows oldest first, floats)."""
    out = action_factors(rows, actions) if actions else {}
    for i in range(1, len(rows)):
        if i in out:
            continue
        last_close = rows[i - 1].get("close")
        if not last_close:
            continue
        prev_close = rows[i].get("prev_close")
        if prev_close:
            ratio = prev_close / last_close
            if abs(ratio - 1) > THRESHOLD:
                out[i] = ratio
                continue
        if actions is not None:
            continue  # recorded actions replace the gap heuristic
        price = rows[i].get("open") or rows[i].get("close")
        if not price:
            continue
        gap = price / last_close
        if gap <= 1 - MIN_GAP:
            nearest = min(STANDARD_FACTORS, key=lambda f: abs(gap / f - 1))
            if abs(gap / nearest - 1) <= GAP_TOLERANCE:
                out[i] = nearest
    return out


def adjust(rows: list[dict], actions: list[dict] | None = None) -> list[dict]:
    """Return copies of `rows` (oldest first, floats) with OHLC back-adjusted and volume scaled."""
    out = [dict(r) for r in rows]
    events = split_factors(rows, actions)
    factor = 1.0
    for i in range(len(out) - 1, 0, -1):
        if i in events:
            factor *= events[i]
        if factor != 1.0:
            r = out[i - 1]
            for k in PRICE_KEYS:
                if r.get(k) is not None:
                    r[k] = r[k] * factor
            if r.get("prev_close") is not None:
                r["prev_close"] = r["prev_close"] * factor
            if r.get("volume") is not None:
                r["volume"] = int(r["volume"] / factor)
    return out
