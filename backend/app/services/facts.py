"""'Did you know?' facts, computed only from data we hold (filings, NSE prices, NSE listing).

Every fact carries its source so users can verify it. No free-text generation, no outside claims.
"""

import re
from datetime import date
from decimal import Decimal

from app.services.adjust import adjust, split_factors
from app.services.compliance import filter_compliant

MAX_DAILY_MOVE = 0.6  # ignore >60% one-day moves (relistings / data errors)

BHAV = "NSE bhavcopy"
BHAV_ADJ = "NSE bhavcopy (split/bonus-adjusted)"
MCAP = "genScr market cap (price × shares)"
FILINGS = "Annual results filings"


def _f(v):
    return float(v) if isinstance(v, Decimal) else v


def inr(n: float, decimals: int = 0) -> str:
    """Indian digit grouping: 1234567 -> 12,34,567."""
    neg = n < 0
    whole, _, frac = f"{abs(n):.{decimals}f}".partition(".")
    if len(whole) > 3:
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", whole[:-3])
        whole = f"{head},{whole[-3:]}"
    return ("-" if neg else "") + whole + (f".{frac}" if frac else "")


def fy_label(d: date) -> str:
    return f"FY{(d.year if d.month <= 3 else d.year + 1) % 100:02d}"


def _dmy(d: date) -> str:
    return d.strftime("%-d %b %Y")


def build_facts(stock: dict, prices: list[dict], fy: list[dict], rank: dict | None, today: date | None = None) -> list[dict]:
    """`prices` oldest first; `fy` newest first."""
    today = today or date.today()
    stock = {k: _f(v) for k, v in stock.items()}
    fy = [{k: _f(v) for k, v in r.items()} for r in fy]
    facts: list[dict] = []

    def add(id_, icon, title, text, source):
        facts.append({"id": id_, "icon": icon, "title": title, "text": text, "source": source})

    # --- From filings -------------------------------------------------------
    if fy:
        latest = fy[0]
        label = fy_label(latest["period_end"])
        src = f"{label} {latest.get('source') or 'results'} filing"
        np_ = latest.get("net_profit")
        if np_:
            per_day = np_ / 365
            if np_ > 0:
                hourly = per_day / 24
                per_hour = f"₹{hourly:.1f} Cr" if hourly >= 1 else f"₹{hourly * 100:.1f} lakh"
                add("profit_per_day", "coins", "Profit machine",
                    f"Earned ₹{inr(per_day, 1 if per_day < 100 else 0)} Cr of profit every single day in {label}, "
                    f"about {per_hour} an hour.", src)
            else:
                add("loss_per_day", "flame", "Burning cash", f"Lost about ₹{inr(-per_day, 1)} Cr per day in {label}.", src)

        if latest.get("total_debt") == 0 and latest.get("total_assets"):
            add("debt_free", "shield", "Debt-free",
                f"Reported zero borrowings on its balance sheet as of {_dmy(latest['period_end'])}.", src)

        cash, mcap = latest.get("cash"), stock.get("market_cap")
        if cash and mcap and cash / mcap >= 0.1:
            add("cash_pile", "wallet", "Cash pile",
                f"Holds ₹{inr(cash)} Cr in cash and equivalents, {cash / mcap * 100:.0f}% of its entire market value.", src)

        oldest = fy[-1]
        r0, r1 = oldest.get("revenue"), latest.get("revenue")
        if len(fy) >= 2 and r0 and r1 and r0 > 0:
            mult = r1 / r0
            span = f"{fy_label(oldest['period_end'])} to {label}"
            if mult >= 1.5:
                add("revenue_multiple", "trending", "Growth spurt",
                    f"Revenue grew {mult:.1f}x from ₹{inr(r0)} Cr to ₹{inr(r1)} Cr ({span}).", FILINGS)
            elif mult <= 0.75:
                add("revenue_shrink", "trending-down", "Shrinking sales",
                    f"Revenue fell {(1 - mult) * 100:.0f}% from ₹{inr(r0)} Cr to ₹{inr(r1)} Cr ({span}).", FILINGS)

    # --- From NSE listing / ranks --------------------------------------------
    listed = stock.get("listing_date")
    if listed:
        years = (today - listed).days // 365
        if years >= 1:
            add("listed_since", "calendar", "Market veteran" if years >= 20 else "On the exchange",
                f"Listed on NSE since {_dmy(listed)}, {years} years of public trading.", "NSE equity list")

    if rank and rank.get("total", 0) >= 100:
        if rank["rank"] <= 50:
            add("mcap_rank", "crown", "Heavyweight",
                f"#{rank['rank']} most valuable of the {rank['total']} NSE companies genScr tracks.", MCAP)
        if stock.get("sector") and rank.get("sector_rank") == 1 and rank.get("sector_total", 0) >= 5:
            add("sector_leader", "trophy", "Sector leader",
                f"The most valuable company in {stock['sector']} among {rank['sector_total']} tracked peers.", MCAP)
        elif stock.get("sector") and rank.get("sector_rank", 99) <= 3 and rank.get("sector_total", 0) >= 5:
            add("sector_top3", "trophy", "Top of its class",
                f"#{rank['sector_rank']} most valuable in {stock['sector']} among {rank['sector_total']} tracked peers.", MCAP)

    # --- From prices -----------------------------------------------------------
    rows = [{k: _f(v) for k, v in r.items()} for r in prices]
    if len(rows) >= 250:
        since = _dmy(rows[0]["trade_date"])
        events = split_factors(rows)  # bonus/split days aren't real moves
        moves = [
            (r["close"] / r["prev_close"] - 1, r["trade_date"])
            for i, r in enumerate(rows)
            if i not in events and r.get("close") and r.get("prev_close")
            and abs(r["close"] / r["prev_close"] - 1) <= MAX_DAILY_MOVE
        ]
        if moves:
            best, worst = max(moves), min(moves)
            if best[0] >= 0.05:
                add("best_day", "zap", "Biggest single-day jump",
                    f"+{best[0] * 100:.1f}% on {_dmy(best[1])}, its best session since {since}.", BHAV)
            if worst[0] <= -0.05:
                add("worst_day", "zap-off", "Toughest day",
                    f"{worst[0] * 100:.1f}% on {_dmy(worst[1])}, its worst session since {since}.", BHAV)

        streak = best_streak = 0
        streak_end = None
        for r in rows:
            if r.get("close") and r.get("prev_close") and r["close"] > r["prev_close"]:
                streak += 1
                if streak > best_streak:
                    best_streak, streak_end = streak, r["trade_date"]
            else:
                streak = 0
        if best_streak >= 7:
            add("win_streak", "flame", "Hot streak",
                f"Rose {best_streak} sessions in a row, its longest winning run since {since} (ended {_dmy(streak_end)}).", BHAV)

        adj = adjust(rows)
        peak = max(adj, key=lambda r: r["close"] or 0)
        cur = adj[-1]["close"]
        if peak["close"] and cur:
            gap = (cur / peak["close"] - 1) * 100
            text = (f"Closed at its highest level since {since} on {_dmy(peak['trade_date'])}"
                    + (" and is right there now." if gap > -2 else f"; it trades {abs(gap):.0f}% below that peak today."))
            add("peak", "mountain", "Record watch", text, BHAV_ADJ)

        year_end: dict[int, float] = {}
        for r in adj:
            year_end[r["trade_date"].year] = r["close"]
        years_sorted = sorted(year_end)
        full = [y for y in years_sorted[1:] if y < today.year]
        if len(full) >= 4:
            ups = sum(1 for y in full if year_end[y] > year_end[y - 1])
            add("up_years", "calendar-check", "Consistency check",
                f"Ended higher in {ups} of {len(full)} calendar years ({full[0]} to {full[-1]}).", BHAV_ADJ)

    priority = ["profit_per_day", "loss_per_day", "best_day", "mcap_rank", "sector_leader", "revenue_multiple", "debt_free",
                "cash_pile", "win_streak", "up_years", "peak", "worst_day", "sector_top3", "revenue_shrink", "listed_since"]
    facts = filter_compliant(facts)  # defence in depth: never show advice-like wording
    return sorted(facts, key=lambda f: priority.index(f["id"]) if f["id"] in priority else 99)
