"""Company timeline events from listing data, corporate actions and price history (pure, no I/O).

Dividends are summarised per financial year to keep the timeline readable; every event is factual
and cites its source.
"""

from datetime import date

from app.services.adjust import adjust
from app.services.compliance import filter_compliant
from app.services.dividends import fy_of
from app.services.facts import inr

NSE_CA = "NSE corporate actions"


def _ev(d: date, kind: str, title: str, text: str, source: str) -> dict:
    return {"date": d.isoformat(), "kind": kind, "title": title, "text": text, "source": source}


def build_timeline(stock: dict, actions: list[dict], prices: list[dict]) -> list[dict]:
    """stock: stocks row; actions: corporate_actions rows; prices: raw [{trade_date, open, high, low, close, prev_close}]."""
    events: list[dict] = []
    if stock.get("listing_date"):
        events.append(_ev(stock["listing_date"], "listing", "Listed on NSE",
                          f"{stock.get('name') or stock['symbol']} began trading on the National Stock Exchange.",
                          "NSE equity list"))

    divs = sorted((a for a in actions if a["kind"] == "dividend" and a.get("amount")), key=lambda a: a["ex_date"])
    if divs:
        first = divs[0]
        events.append(_ev(first["ex_date"], "milestone", "First dividend on record",
                          f"₹{first['amount']:g} per share (ex-date). Records start in 2005.", NSE_CA))
    by_fy: dict[int, list] = {}
    for a in divs:
        by_fy.setdefault(fy_of(a["ex_date"]), []).append(a)
    for fy, items in sorted(by_fy.items()):
        total = sum(a["amount"] for a in items)
        n = len(items)
        events.append(_ev(items[-1]["ex_date"], "dividend", f"FY{fy % 100:02d} dividends",
                          f"₹{inr(total, 2)} per share across {n} payment{'s' if n > 1 else ''}.", NSE_CA))

    for a in sorted((a for a in actions if a["kind"] != "dividend"), key=lambda a: a["ex_date"]):
        k = a["kind"]
        if k == "bonus":
            events.append(_ev(a["ex_date"], "bonus", f"Bonus issue {a['ratio_new']}:{a['ratio_held']}",
                              f"{a['ratio_new']} free share{'s' if a['ratio_new'] > 1 else ''} for every "
                              f"{a['ratio_held']} held.", NSE_CA))
        elif k == "split":
            events.append(_ev(a["ex_date"], "split", "Stock split",
                              f"Face value split from ₹{a['old_fv']:g} to ₹{a['new_fv']:g}: each share became "
                              f"{a['old_fv'] / a['new_fv']:g}.", NSE_CA))
        elif k == "rights":
            ratio = f" {a['ratio_new']}:{a['ratio_held']}" if a.get("ratio_new") else ""
            price = f" at ₹{a['price']:g}" if a.get("price") else ""
            events.append(_ev(a["ex_date"], "rights", f"Rights issue{ratio}", f"Shareholders were offered new shares{price}.",
                              NSE_CA))
        elif k == "buyback":
            events.append(_ev(a["ex_date"], "buyback", "Share buyback", "The company bought back its own shares.", NSE_CA))
        elif k == "demerger":
            events.append(_ev(a["ex_date"], "demerger", "Demerger",
                              "A business was separated into a new listed company.", NSE_CA))

    rows = [p for p in prices if p.get("close")]
    if len(rows) >= 250:
        adj = adjust(rows, actions or None)
        since = rows[0]["trade_date"].year
        peak = max(adj, key=lambda r: r["close"])
        events.append(_ev(peak["trade_date"], "high", "Highest close in our data",
                          f"Closed at ₹{inr(peak['close'], 2)} (split/bonus-adjusted), the highest since {since}.",
                          "NSE bhavcopy"))
        # Deepest fall from a running peak, and its trough date
        run_peak, worst, trough, peak_at = adj[0]["close"], 0.0, None, None
        cur_peak_date = adj[0]["trade_date"]
        for r in adj:
            if r["close"] > run_peak:
                run_peak, cur_peak_date = r["close"], r["trade_date"]
            dd = r["close"] / run_peak - 1
            if dd < worst:
                worst, trough, peak_at = dd, r["trade_date"], cur_peak_date
        if trough and worst <= -0.2:
            events.append(_ev(trough, "drawdown", "Deepest fall",
                              f"Fell {abs(worst) * 100:.0f}% from its {peak_at:%b %Y} peak, the largest decline since {since}.",
                              "NSE bhavcopy (split/bonus-adjusted)"))

    events = filter_compliant(events)
    return sorted(events, key=lambda e: e["date"])
