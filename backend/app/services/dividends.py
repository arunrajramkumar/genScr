"""Dividend history analytics (pure, no I/O).

Amounts are stored as declared. For year-on-year comparison we also restate each payment in
today's share terms (divide out later bonuses and splits), so a ₹10 dividend before a 1:1 bonus
compares as ₹5 today.
"""

from bisect import bisect_right
from datetime import date


def fy_of(d: date) -> int:
    """Indian financial year ending in March: 15 May 2025 -> FY2026."""
    return d.year + 1 if d.month >= 4 else d.year


def share_factor_after(d: date, actions: list[dict]) -> float:
    """Multiplier converting a per-share amount on date `d` into today's share terms."""
    f = 1.0
    for a in actions:
        if a["ex_date"] <= d:
            continue
        if a["kind"] == "bonus" and a.get("ratio_held"):
            f *= a["ratio_held"] / (a["ratio_held"] + a["ratio_new"])
        elif a["kind"] == "split" and a.get("old_fv"):
            f *= a["new_fv"] / a["old_fv"]
    return f


def ttm_dividend_yield(actions: list[dict], as_of: date, close: float | None) -> float | None:
    """Dividends ex-dated in the 12 months to `as_of`, in today's share terms, as % of `close`."""
    if not close:
        return None
    start = date(as_of.year - 1, as_of.month, min(as_of.day, 28))
    total = sum(
        a["amount"] * share_factor_after(a["ex_date"], actions)
        for a in actions
        if a["kind"] == "dividend" and a.get("amount") and start < a["ex_date"] <= as_of
    )
    return round(total / close * 100, 2)


def _close_on_or_before(d: date, dates: list[date], closes: list[float]) -> float | None:
    i = bisect_right(dates, d) - 1
    return closes[i] if i >= 0 else None


def dividend_history(actions: list[dict], prices: list[dict], today: date | None = None) -> dict:
    """actions: corporate actions (any kinds); prices: raw [{trade_date, close}] oldest first."""
    today = today or date.today()
    dates = [p["trade_date"] for p in prices]
    closes = [p["close"] for p in prices]
    divs = sorted((a for a in actions if a["kind"] == "dividend" and a.get("amount")), key=lambda a: a["ex_date"])

    payments = []
    for a in divs:
        close = _close_on_or_before(a["ex_date"], dates, closes)
        payments.append({
            "ex_date": a["ex_date"].isoformat(),
            "amount": a["amount"],
            "adjusted_amount": round(a["amount"] * share_factor_after(a["ex_date"], actions), 4),
            "yield_pct": round(a["amount"] / close * 100, 2) if close else None,
            "subject": a.get("subject"),
        })

    by_fy: dict[int, dict] = {}
    for a, p in zip(divs, payments, strict=True):
        fy = fy_of(a["ex_date"])
        row = by_fy.setdefault(fy, {"fy": fy, "declared": 0.0, "adjusted": 0.0, "payments": 0})
        row["declared"] += a["amount"]
        row["adjusted"] += p["adjusted_amount"]
        row["payments"] += 1
    years = []
    for fy in sorted(by_fy):
        row = by_fy[fy]
        fy_end = date(fy, 3, 31)
        close = _close_on_or_before(min(fy_end, today), dates, closes)
        factor_now = share_factor_after(min(fy_end, today), actions)
        # yield on the FY-end price, both in that year's share terms
        row["yield_pct"] = round(row["declared"] / close * 100, 2) if close and factor_now else None
        row["declared"] = round(row["declared"], 4)
        row["adjusted"] = round(row["adjusted"], 4)
        years.append(row)

    current_fy = fy_of(today)
    complete = [y for y in years if y["fy"] < current_fy]
    streak = 0
    expected = current_fy - 1
    for y in reversed(complete):
        if y["fy"] != expected:
            break
        streak += 1
        expected -= 1

    growth_streak = 0
    for prev, cur in zip(reversed(complete[:-1]), reversed(complete), strict=False):
        if cur["fy"] - prev["fy"] != 1 or cur["adjusted"] <= prev["adjusted"]:
            break
        growth_streak += 1

    cagr_5y = None
    by_year = {y["fy"]: y["adjusted"] for y in complete}
    last = current_fy - 1
    if by_year.get(last) and by_year.get(last - 5):
        cagr_5y = round(((by_year[last] / by_year[last - 5]) ** (1 / 5) - 1) * 100, 2)

    return {
        "payments": payments,
        "years": years,
        "stats": {
            "total_payments": len(payments),
            "first_dividend": payments[0]["ex_date"] if payments else None,
            "paying_streak_years": streak,
            "growth_streak_years": growth_streak,
            "dps_cagr_5y": cagr_5y,
            "last_fy": complete[-1] if complete else None,
            "total_adjusted_since_first": round(sum(p["adjusted_amount"] for p in payments), 2),
        },
    }
