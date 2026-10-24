"""Trailing P/E and P/B over the stock's own history (pure, no I/O).

How the numbers are built:
- Prices are the raw NSE closes. Each week is sampled at its last trading day.
- A filing counts from its public date, not its period end: period end + 45 days for quarters and
  + 60 days for FY and the March quarter (Q4 is published with the annual results). Nothing is used earlier.
- EPS and share counts are per-share figures on the share basis of the day they were published. They are
  restated to the basis of the price date with the split/bonus factors from adjust.split_factors, the same
  factors the price charts use. So a split does not move P/E: earlier filings are restated, later ones already match.
  (Equivalent to adjusting prices and EPS both to the latest basis.)
- Trailing EPS is the last four quarters when they are consecutive and public; otherwise the latest public FY EPS.
  A period ending more than STALE_DAYS before the date is not trailing.
- P/E is undefined when trailing EPS is zero or negative: those weeks are counted in loss_weeks, not plotted.
- P/B = market cap (close x share count on that date) / latest public total equity.
"""

from datetime import date, timedelta
from statistics import median

from app.services.adjust import split_factors

PUBLIC_LAG_DAYS = {"Q": 45, "FY": 60}
STALE_DAYS = 400  # a period ending longer ago than this is not trailing
WINDOW_DAYS = 3653  # ten years of weekly points at most
MIN_POINTS = 52  # about a year of weekly points; shorter series are not shown


def _filings(rows: list[dict]) -> list[dict]:
    """Fundamentals rows with their public date added, newest period first."""
    out = []
    for r in rows:
        annual = r["period_type"] == "FY" or r["period_end"].month == 3  # March quarter is filed with the annual results
        out.append({**r, "public": r["period_end"] + timedelta(days=PUBLIC_LAG_DAYS["FY" if annual else "Q"])})
    return sorted(out, key=lambda f: f["period_end"], reverse=True)


def _events(rows: list[dict], actions: list[dict] | None) -> list[tuple[date, float]]:
    """(trade date, factor) for each split / bonus break in the prices, oldest first."""
    return sorted((rows[i]["trade_date"], f) for i, f in split_factors(rows, actions or None).items())


def _through(events: list[tuple[date, float]], d: date) -> float:
    """Product of the factors on or before `d`: the price basis on that day."""
    f = 1.0
    for ed, ef in events:
        if ed > d:
            break
        f *= ef
    return f


def _restate(events: list[tuple[date, float]], src: date, dst: date) -> float:
    """Multiplier that moves a per-share figure from the share basis of `src` to that of `dst`."""
    return _through(events, dst) / _through(events, src)


def _latest(filings: list[dict], field: str, on: date) -> dict | None:
    """Newest filing public by `on` that reports `field`, unless it is stale."""
    earliest = on - timedelta(days=STALE_DAYS)
    return next((f for f in filings if f["public"] <= on and f.get(field) is not None and f["period_end"] >= earliest), None)


def _consecutive(quarters: list[dict]) -> bool:
    """True when the quarters (newest first) each end exactly three months before the next one."""
    months = [f["period_end"].year * 12 + f["period_end"].month for f in quarters]
    return all(a - b == 3 for a, b in zip(months, months[1:], strict=False))


def trailing_eps(filings: list[dict], events: list[tuple[date, float]], on: date) -> float | None:
    """Trailing EPS known on `on`, on the share basis of `on`. None when no usable EPS is public yet."""
    earliest = on - timedelta(days=STALE_DAYS)
    public = [f for f in filings if f["public"] <= on and f.get("eps") is not None and f["period_end"] >= earliest]
    fy = next((f for f in public if f["period_type"] == "FY"), None)
    quarters = [f for f in public if f["period_type"] == "Q"][:4]
    # Four quarters are used only when they cover the last twelve months and are at least as recent as the latest FY.
    if len(quarters) == 4 and _consecutive(quarters) and (fy is None or quarters[0]["period_end"] >= fy["period_end"]):
        return sum(f["eps"] * _restate(events, f["public"], on) for f in quarters)
    return fy["eps"] * _restate(events, fy["public"], on) if fy else None


def pb_at(filings: list[dict], events: list[tuple[date, float]], on: date, close: float) -> float | None:
    """Market cap (close x shares on `on`, in ₹ crore) over the latest public total equity (₹ crore)."""
    eq = _latest(filings, "total_equity", on)
    sh = _latest(filings, "shares_outstanding", on)
    if not eq or not sh or eq["total_equity"] <= 0:
        return None
    shares = sh["shares_outstanding"] / _restate(events, sh["public"], on)  # shares move opposite to EPS
    return close * shares / 1e7 / eq["total_equity"]


def _weekly(rows: list[dict]) -> list[dict]:
    """Last trading day of each ISO week."""
    weeks: dict[tuple[int, int], dict] = {}
    for r in rows:
        weeks[r["trade_date"].isocalendar()[:2]] = r
    return list(weeks.values())


def _r(v: float | None) -> float | None:
    return None if v is None else round(v, 2)


def _summary(points: list[tuple[date, float]], as_of: date, loss_weeks: int = 0) -> dict | None:
    if len(points) < MIN_POINTS:
        if loss_weeks < MIN_POINTS:
            return None
        # Loss-making for about a year or more: no P/E to plot, but say so rather than hide the series.
        return {"current": None, "min": None, "median": None, "max": None, "percentile": None, "since": None,
                "years": None, "loss_weeks": loss_weeks, "points": []}
    values = [v for _, v in points]
    last_day, last = points[-1]
    current = last if last_day == as_of else None  # None when the latest day has no value (e.g. loss-making)
    return {
        "current": _r(current),
        "min": _r(min(values)),
        "median": _r(median(values)),
        "max": _r(max(values)),
        "percentile": round(100 * sum(v < current for v in values) / len(values)) if current is not None else None,
        "since": points[0][0].isoformat(),
        "years": round((last_day - points[0][0]).days / 365.25, 1),
        "loss_weeks": loss_weeks,
        "points": [{"time": d.isoformat(), "value": _r(v)} for d, v in points],
    }


def valuation_history(rows: list[dict], fundamentals: list[dict], actions: list[dict] | None = None) -> dict | None:
    """Weekly trailing P/E and P/B over the last ten years.

    rows: daily prices, oldest first ({trade_date, open, close, prev_close}).
    fundamentals: {period_end, period_type, eps, total_equity, shares_outstanding} rows.
    actions: corporate_actions rows, or None to fall back to the price-gap heuristic.
    Returns None without prices. A series is None when it has fewer than MIN_POINTS weeks.
    """
    rows = [r for r in rows if r.get("close")]
    if not rows:
        return None
    as_of = rows[-1]["trade_date"]
    since = as_of - timedelta(days=WINDOW_DAYS)
    events = _events(rows, actions)
    filings = _filings(fundamentals)
    pe, pb, loss_weeks = [], [], 0
    for r in _weekly(rows):
        d, close = r["trade_date"], float(r["close"])
        if d < since:
            continue
        eps = trailing_eps(filings, events, d)
        if eps is not None:
            if eps > 0:
                pe.append((d, close / eps))
            else:
                loss_weeks += 1
        mult = pb_at(filings, events, d, close)
        if mult is not None:
            pb.append((d, mult))
    return {"as_of": as_of.isoformat(), "pe": _summary(pe, as_of, loss_weeks), "pb": _summary(pb, as_of)}
