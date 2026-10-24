"""Stock vs index (pure, no I/O): growth, relative strength, returns, beta, capture ratios, calendar years.

Both series are price-only (the stock split/bonus-adjusted, the index a price index), so dividends are left out on
both sides and the comparison stays like for like.
"""

import math
from datetime import date

WEEKS_PER_YEAR = 52


def _align(stock: list[dict], index: list[dict]) -> list[tuple[date, float, float]]:
    """Days both traded, oldest first."""
    idx = {r["trade_date"]: r["close"] for r in index if r.get("close")}
    return [(r["trade_date"], r["close"], idx[r["trade_date"]]) for r in stock if r.get("close") and r["trade_date"] in idx]


def _weekly(rows: list[tuple[date, float, float]]) -> list[tuple[date, float, float]]:
    out, last = [], None
    for r in rows:
        wk = r[0].isocalendar()[:2]
        if wk == last:
            out[-1] = r
        else:
            out.append(r)
            last = wk
    return out


def _monthly(rows: list[tuple[date, float, float]]) -> list[tuple[date, float, float]]:
    out, last = [], None
    for r in rows:
        if (r[0].year, r[0].month) == last:
            out[-1] = r
        else:
            out.append(r)
            last = (r[0].year, r[0].month)
    return out


def _on_or_before(rows: list[tuple[date, float, float]], d: date) -> tuple[date, float, float] | None:
    best = None
    for r in rows:
        if r[0] > d:
            break
        best = r
    return best if best and (d - best[0]).days <= 10 else None


def _pct(a: float, b: float) -> float:
    return round((b / a - 1) * 100, 2)


def _returns(rows: list[tuple[date, float, float]]) -> list[dict]:
    end = rows[-1]
    out = []
    for label, days, years in (("1M", 30, 0), ("6M", 182, 0), ("1Y", 365, 1), ("3Y", 3 * 365, 3), ("5Y", 5 * 365, 5)):
        base = _on_or_before(rows, date.fromordinal(end[0].toordinal() - days))
        if not base:
            continue
        if years > 1:  # annualised, like the CAGR figures elsewhere
            s = round(((end[1] / base[1]) ** (1 / years) - 1) * 100, 2)
            i = round(((end[2] / base[2]) ** (1 / years) - 1) * 100, 2)
        else:
            s, i = _pct(base[1], end[1]), _pct(base[2], end[2])
        out.append({"period": label, "annualised": years > 1, "stock": s, "index": i, "difference": round(s - i, 2)})
    return out


def _max_drawdown(values: list[float]) -> float:
    peak, worst = values[0], 0.0
    for v in values:
        peak = max(peak, v)
        worst = min(worst, v / peak - 1)
    return round(worst * 100, 2)


def _stats(weekly: list[tuple[date, float, float]], monthly: list[tuple[date, float, float]]) -> dict | None:
    rs = [(b[1] / a[1] - 1, b[2] / a[2] - 1) for a, b in zip(weekly, weekly[1:], strict=False)]
    if len(rs) < 26:
        return None
    n = len(rs)
    ms = sum(s for s, _ in rs) / n
    mi = sum(i for _, i in rs) / n
    cov = sum((s - ms) * (i - mi) for s, i in rs) / (n - 1)
    var_s = sum((s - ms) ** 2 for s, _ in rs) / (n - 1)
    var_i = sum((i - mi) ** 2 for _, i in rs) / (n - 1)
    mr = [(b[1] / a[1] - 1, b[2] / a[2] - 1) for a, b in zip(monthly, monthly[1:], strict=False)]
    up = [(s, i) for s, i in mr if i > 0]
    down = [(s, i) for s, i in mr if i < 0]

    def capture(pairs):  # average stock move as a % of the average index move in those months
        if len(pairs) < 3:
            return None
        avg_i = sum(i for _, i in pairs) / len(pairs)
        return round(sum(s for s, _ in pairs) / len(pairs) / avg_i * 100, 1) if avg_i else None

    return {
        "beta": round(cov / var_i, 2) if var_i else None,
        "correlation": round(cov / math.sqrt(var_s * var_i), 2) if var_s and var_i else None,
        "volatility_stock": round(math.sqrt(var_s * WEEKS_PER_YEAR) * 100, 1),
        "volatility_index": round(math.sqrt(var_i * WEEKS_PER_YEAR) * 100, 1),
        "max_drawdown_stock": _max_drawdown([r[1] for r in weekly]),
        "max_drawdown_index": _max_drawdown([r[2] for r in weekly]),
        "up_capture": capture(up),
        "down_capture": capture(down),
        "months": len(mr),
        "months_ahead": sum(1 for s, i in mr if s > i),
        "weeks": n,
    }


def _calendar(rows: list[tuple[date, float, float]]) -> list[dict]:
    """Per calendar year, from the last close of the previous year (or the first day held, marked partial)."""
    out, prev = [], None
    years = sorted({r[0].year for r in rows})
    for y in years:
        in_year = [r for r in rows if r[0].year == y]
        base = prev or in_year[0]
        end = in_year[-1]
        out.append({"year": y, "stock": _pct(base[1], end[1]), "index": _pct(base[2], end[2]),
                    "partial": prev is None or y == rows[-1][0].year and end[0].month < 12})
        prev = end
    return out


def compare_to_index(stock: list[dict], index: list[dict], years: int) -> dict | None:
    """stock/index: [{trade_date, close}] oldest first (stock already split-adjusted)."""
    rows = _align(stock, index)
    if len(rows) < 30:
        return None
    end = rows[-1][0]
    start = date(end.year - years, end.month, min(end.day, 28))
    window = [r for r in rows if r[0] >= start] or rows
    week = _weekly(window)
    s0, i0 = week[0][1], week[0][2]
    return {
        "start": window[0][0].isoformat(),
        "end": end.isoformat(),
        "available_years": round((end - rows[0][0]).days / 365.25, 1),
        "series": [{"time": d.isoformat(), "stock": round(s / s0 * 100, 2), "index": round(i / i0 * 100, 2),
                    "relative": round((s / s0) / (i / i0) * 100, 2)} for d, s, i in week],
        "returns": _returns(rows),
        "stats": _stats(week, _monthly(window)),
        "calendar": _calendar(rows)[-10:],
    }
