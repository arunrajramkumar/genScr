"""Side-by-side risk and return for 2-5 stocks (pure, no I/O).

Input series are split/bonus-adjusted closes, oldest first. Everything is historical and descriptive.
"""

import math
from datetime import date, timedelta

TRADING_DAYS = 252


def window(rows: list[dict], years: int) -> list[dict]:
    """Rows within `years` of the last trading day."""
    if not rows:
        return []
    since = rows[-1]["trade_date"] - timedelta(days=round(365.25 * years))
    return [r for r in rows if r["trade_date"] >= since and r.get("close")]


def rebased(rows: list[dict], weekly: bool = False) -> list[dict]:
    """Closes rebased to 100 at the first day; weekly keeps the last day of each ISO week (plus the final day)."""
    if not rows:
        return []
    base = float(rows[0]["close"])
    pts, last_week = [], None
    for r in rows:
        wk = r["trade_date"].isocalendar()[:2]
        p = {"time": r["trade_date"].isoformat(), "value": round(float(r["close"]) / base * 100, 2)}
        if weekly and wk == last_week and len(pts) > 1:  # the first day stays as the base
            pts[-1] = p
        else:
            pts.append(p)
        last_week = wk
    return pts


def daily_returns(rows: list[dict]) -> dict[date, float]:
    out = {}
    for prev, cur in zip(rows, rows[1:], strict=False):
        p, c = float(prev["close"]), float(cur["close"])
        if p > 0 and c > 0:
            out[cur["trade_date"]] = c / p - 1
    return out


def _stdev(xs: list[float]) -> float | None:
    if len(xs) < 20:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def correlation(a: dict[date, float], b: dict[date, float]) -> float | None:
    common = sorted(a.keys() & b.keys())
    if len(common) < 20:
        return None
    xs, ys = [a[d] for d in common], [b[d] for d in common]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    vx, vy = sum((x - mx) ** 2 for x in xs), sum((y - my) ** 2 for y in ys)
    return round(cov / math.sqrt(vx * vy), 2) if vx and vy else None


def beta(stock: dict[date, float], index: dict[date, float]) -> float | None:
    common = sorted(stock.keys() & index.keys())
    if len(common) < 20:
        return None
    xs, ys = [index[d] for d in common], [stock[d] for d in common]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    var = sum((x - mx) ** 2 for x in xs)
    return round(sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / var, 2) if var else None


def drawdown(rows: list[dict]) -> dict | None:
    """Largest peak-to-trough fall, with dates, and whether the price has since regained the peak."""
    if len(rows) < 2:
        return None
    peak, peak_date = float(rows[0]["close"]), rows[0]["trade_date"]
    worst = {"pct": 0.0, "peak": peak_date, "trough": peak_date, "peak_close": peak}
    for r in rows:
        c = float(r["close"])
        if c > peak:
            peak, peak_date = c, r["trade_date"]
        dd = c / peak - 1
        if dd < worst["pct"]:
            worst = {"pct": dd, "peak": peak_date, "trough": r["trade_date"], "peak_close": peak}
    recovered = next(
        (r["trade_date"] for r in rows if r["trade_date"] > worst["trough"] and float(r["close"]) >= worst["peak_close"]), None
    )
    return {
        "pct": round(worst["pct"] * 100, 2),
        "peak": worst["peak"].isoformat(),
        "trough": worst["trough"].isoformat(),
        "recovered": recovered.isoformat() if recovered else None,
        "current_pct": round((float(rows[-1]["close"]) / max(float(r["close"]) for r in rows) - 1) * 100, 2),
    }


def stats(rows: list[dict], index_returns: dict[date, float], years: int) -> dict | None:
    if len(rows) < 2:
        return None
    rets = daily_returns(rows)
    vals = list(rets.values())
    first, last = float(rows[0]["close"]), float(rows[-1]["close"])
    span = (rows[-1]["trade_date"] - rows[0]["trade_date"]).days / 365.25
    sd = _stdev(vals)
    best = max(rets.items(), key=lambda kv: kv[1]) if rets else None
    worst = min(rets.items(), key=lambda kv: kv[1]) if rets else None
    return {
        "since": rows[0]["trade_date"].isoformat(),
        "full_window": span >= years - 0.05,
        "total_return": round((last / first - 1) * 100, 2),
        "cagr": round(((last / first) ** (1 / span) - 1) * 100, 2) if span >= 1 else None,
        "volatility": round(sd * math.sqrt(TRADING_DAYS) * 100, 2) if sd is not None else None,
        "drawdown": drawdown(rows),
        "beta": beta(rets, index_returns),
        "best_day": {"date": best[0].isoformat(), "pct": round(best[1] * 100, 2)} if best else None,
        "worst_day": {"date": worst[0].isoformat(), "pct": round(worst[1] * 100, 2)} if worst else None,
        "up_days_pct": round(sum(1 for v in vals if v > 0) / len(vals) * 100, 1) if vals else None,
    }


def correlations(returns: dict[str, dict[date, float]]) -> list[dict]:
    syms = list(returns)
    return [
        {"a": a, "b": b, "value": correlation(returns[a], returns[b])}
        for i, a in enumerate(syms) for b in syms[i + 1:]
    ]
