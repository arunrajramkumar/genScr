"""Historical risk profile from split/bonus-adjusted closes (pure, no I/O): drawdowns, volatility,
calendar-year and monthly returns (seasonality). Descriptive statistics only."""

import math
from datetime import date


def _drawdown_episodes(rows: list[dict]) -> list[dict]:
    """Non-overlapping peak -> trough -> recovery episodes, deepest first."""
    episodes, peak, peak_date, trough, trough_date = [], None, None, None, None
    for r in rows:
        c, d = r["close"], r["trade_date"]
        if peak is None or c >= peak:
            if peak is not None and trough is not None and trough < peak:
                episodes.append({"peak": peak_date, "trough": trough_date, "depth": trough / peak - 1, "recovered": d})
            peak, peak_date, trough, trough_date = c, d, None, None
        elif trough is None or c < trough:
            trough, trough_date = c, d
    if peak is not None and trough is not None and trough < peak:
        episodes.append({"peak": peak_date, "trough": trough_date, "depth": trough / peak - 1, "recovered": None})
    episodes.sort(key=lambda e: e["depth"])
    return episodes


def _fmt(e: dict, last: date) -> dict:
    end = e["recovered"] or last
    return {
        "peak_date": e["peak"].isoformat(),
        "trough_date": e["trough"].isoformat(),
        "depth_pct": round(e["depth"] * 100, 2),
        "recovered_date": e["recovered"].isoformat() if e["recovered"] else None,
        "days_to_recover": (e["recovered"] - e["trough"]).days if e["recovered"] else None,
        "days_underwater": (end - e["peak"]).days,
    }


def risk_profile(rows: list[dict]) -> dict | None:
    """rows: adjusted [{trade_date, close}] oldest first."""
    rows = [r for r in rows if r.get("close")]
    if len(rows) < 60:
        return None
    last = rows[-1]["trade_date"]
    closes = [r["close"] for r in rows]

    year = closes[-253:]
    rets = [math.log(b / a) for a, b in zip(year, year[1:], strict=False) if a and b]
    vol = math.sqrt(sum((x - sum(rets) / len(rets)) ** 2 for x in rets) / (len(rets) - 1) * 252) * 100 if len(rets) > 20 else None
    up_days = sum(1 for x in rets if x > 0) / len(rets) * 100 if rets else None

    running_peak, peak_date = closes[0], rows[0]["trade_date"]
    underwater = []
    last_week = None
    for r in rows:
        if r["close"] >= running_peak:
            running_peak, peak_date = r["close"], r["trade_date"]
        wk = r["trade_date"].isocalendar()[:2]
        if wk != last_week:  # weekly samples keep the payload small
            underwater.append({"time": r["trade_date"].isoformat(), "value": round((r["close"] / running_peak - 1) * 100, 2)})
            last_week = wk
    current_dd = closes[-1] / running_peak - 1

    episodes = _drawdown_episodes(rows)
    worst = [_fmt(e, last) for e in episodes[:3]]

    # Calendar-year returns (first year only if the data starts in early January)
    year_end: dict[int, float] = {}
    for r in rows:
        year_end[r["trade_date"].year] = r["close"]
    years_sorted = sorted(year_end)
    calendar = []
    for y in years_sorted:
        prev = year_end.get(y - 1)
        if prev:
            calendar.append({"year": y, "return_pct": round((year_end[y] / prev - 1) * 100, 2), "partial": y == last.year})

    # Monthly returns matrix and seasonality
    month_end: dict[tuple, float] = {}
    for r in rows:
        month_end[(r["trade_date"].year, r["trade_date"].month)] = r["close"]
    keys = sorted(month_end)
    monthly = []
    for prev, cur in zip(keys, keys[1:], strict=False):
        if (cur[0] * 12 + cur[1]) - (prev[0] * 12 + prev[1]) == 1:
            change = (month_end[cur] / month_end[prev] - 1) * 100
            monthly.append({"year": cur[0], "month": cur[1], "return_pct": round(change, 2)})
    complete = [m for m in monthly if (m["year"], m["month"]) != (last.year, last.month)]
    seasonality = []
    for mth in range(1, 13):
        vals = [m["return_pct"] for m in complete if m["month"] == mth]
        if vals:
            seasonality.append({"month": mth, "avg_pct": round(sum(vals) / len(vals), 2),
                                "up": sum(1 for v in vals if v > 0), "years": len(vals)})

    return {
        "since": rows[0]["trade_date"].isoformat(),
        "volatility_1y_pct": round(vol, 2) if vol is not None else None,
        "up_days_1y_pct": round(up_days, 1) if up_days is not None else None,
        "current_drawdown_pct": round(current_dd * 100, 2),
        "peak_date": peak_date.isoformat(),
        "worst_drawdowns": worst,
        "underwater": underwater,
        "calendar_years": calendar,
        "monthly": monthly,
        "seasonality": seasonality,
    }
