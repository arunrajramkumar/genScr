"""Index analytics (pure, no I/O): returns, valuation percentiles, categories, comparisons."""

import re
from bisect import bisect_left
from datetime import date

BROAD = {
    "Nifty 50", "Nifty Next 50", "Nifty 100", "Nifty 200", "Nifty 500", "Nifty Midcap 50", "Nifty Midcap 100",
    "Nifty Midcap 150", "Nifty Midcap Select", "Nifty Smallcap 50", "Nifty Smallcap 100", "Nifty Smallcap 250",
    "Nifty Microcap 250", "Nifty Total Market", "Nifty LargeMidcap 250", "Nifty MidSmallcap 400", "Nifty500 Multicap 50:25:25",
}
SECTOR_WORDS = ("bank", "it", "pharma", "fmcg", "auto", "metal", "realty", "energy", "financial", "media", "psu",
                "healthcare", "consumer durables", "oil & gas", "chemicals", "services sector", "infrastructure",
                "commodities", "consumption", "capital markets", "housing", "mobility", "defence", "tourism")


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def category(name: str) -> str:
    n = name.lower()
    if "g-sec" in n or "bond" in n or "sdl" in n or "aaa" in n or "t-bill" in n or "1d rate" in n:
        return "Bonds & rates"
    if "vix" in n:
        return "Volatility"
    if name in BROAD:
        return "Broad market"
    if any(re.search(rf"\b{re.escape(w)}\b", n) for w in SECTOR_WORDS):
        return "Sector & theme"
    return "Strategy & factor"


MAX_GAP_DAYS = 10  # a base older than this means the history has a hole; better no number than a wrong one


def _close_on_or_before(rows: list[dict], d: date) -> float | None:
    dates = [r["trade_date"] for r in rows]
    i = bisect_left(dates, d)
    if i < len(dates) and dates[i] == d:
        return rows[i]["close"]
    if i == 0 or (d - dates[i - 1]).days > MAX_GAP_DAYS:
        return None
    return rows[i - 1]["close"]


def _ret(rows: list[dict], start: date) -> float | None:
    base = _close_on_or_before(rows, start)
    if not base or rows[0]["trade_date"] > start:
        return None
    return round((rows[-1]["close"] / base - 1) * 100, 2)


def _cagr(rows: list[dict], years: int) -> float | None:
    end = rows[-1]["trade_date"]
    start = date(end.year - years, end.month, min(end.day, 28))
    if rows[0]["trade_date"] > start:
        return None
    base = _close_on_or_before(rows, start)
    return round(((rows[-1]["close"] / base) ** (1 / years) - 1) * 100, 2) if base else None


def percentile_of_latest(values: list[float]) -> float | None:
    """Share of history (in %) at or below the latest value."""
    vals = [v for v in values if v is not None]
    if len(vals) < 50:
        return None
    last = vals[-1]
    return round(sum(1 for v in vals if v <= last) / len(vals) * 100, 1)


def summarize(name: str, rows: list[dict]) -> dict | None:
    """rows: [{trade_date, close, change_pct, pe, pb, div_yield}] oldest first."""
    rows = [r for r in rows if r.get("close")]
    if not rows:
        return None
    last = rows[-1]
    end = last["trade_date"]
    return {
        "name": name,
        "slug": slugify(name),
        "category": category(name),
        "as_of": end.isoformat(),
        "close": last["close"],
        "change_pct": last.get("change_pct"),
        "return_1m": _ret(rows, date.fromordinal(end.toordinal() - 30)),
        "return_ytd": _ret(rows, date(end.year - 1, 12, 31)),
        "return_1y": _ret(rows, date(end.year - 1, end.month, min(end.day, 28))),
        "cagr_3y": _cagr(rows, 3),
        "cagr_5y": _cagr(rows, 5),
        "pe": last.get("pe"),
        "pb": last.get("pb"),
        "div_yield": last.get("div_yield"),
        "pe_percentile": percentile_of_latest([r.get("pe") for r in rows]),
        "pb_percentile": percentile_of_latest([r.get("pb") for r in rows]),
        "since": rows[0]["trade_date"].isoformat(),
    }


def weekly(rows: list[dict], keys: tuple[str, ...]) -> list[dict]:
    """One point per ISO week (last trading day), to keep payloads small."""
    out, last_week = [], None
    for r in rows:
        wk = r["trade_date"].isocalendar()[:2]
        point = {"time": r["trade_date"].isoformat(), **{k: r.get(k) for k in keys}}
        if wk == last_week:
            out[-1] = point
        else:
            out.append(point)
            last_week = wk
    return out


def rebased(rows: list[dict], start: date) -> list[dict]:
    pts = [r for r in rows if r["trade_date"] >= start and r.get("close")]
    if not pts:
        return []
    week = weekly(pts, ("close",))
    base = week[0]["close"]  # rebase on the first plotted point so every line starts at exactly 100
    return [{"time": p["time"], "value": round(p["close"] / base * 100, 2)} for p in week]
