"""Total return of a holding, tracking the real share count through corporate actions (pure, no I/O).

Uses RAW (unadjusted) closing prices plus corporate actions:
- bonus a:b   -> shares *= (a + b) / b
- split X->Y  -> shares *= X / Y
- dividend    -> cash = shares x amount, either kept as cash or reinvested at that day's close
Dividends on a day that also has a bonus/split are paid on the pre-action holding (record-date shares).
Rights issues and buybacks are optional for the holder and are not modelled; demerged shares are
not tracked (their value is excluded) and are reported as a caveat.
"""

from dataclasses import dataclass, field
from datetime import date

ORDER = {"dividend": 0, "bonus": 1, "split": 2}


@dataclass
class Run:
    shares: float
    cash: float = 0.0
    events: list = field(default_factory=list)


def _apply(run: Run, action: dict, close: float, mode: str, record: bool) -> None:
    kind = action["kind"]
    before = run.shares
    if kind == "dividend" and mode != "price":
        received = before * action["amount"]
        if mode == "reinvest":
            run.shares += received / close
        else:
            run.cash += received
        if record:
            run.events.append({"date": action["ex_date"], "kind": "dividend", "per_share": action["amount"],
                               "received": round(received, 2), "shares_after": round(run.shares, 4)})
    elif kind == "bonus":
        run.shares *= (action["ratio_new"] + action["ratio_held"]) / action["ratio_held"]
        if record:
            run.events.append({"date": action["ex_date"], "kind": "bonus",
                               "detail": f"{action['ratio_new']}:{action['ratio_held']}",
                               "shares_added": round(run.shares - before, 4), "shares_after": round(run.shares, 4)})
    elif kind == "split":
        run.shares *= action["old_fv"] / action["new_fv"]
        if record:
            run.events.append({"date": action["ex_date"], "kind": "split",
                               "detail": f"₹{action['old_fv']:g} → ₹{action['new_fv']:g}",
                               "shares_added": round(run.shares - before, 4), "shares_after": round(run.shares, 4)})


def total_return(prices: list[dict], actions: list[dict], start: date, amount: float = 10_000) -> dict | None:
    """prices: [{trade_date, close}] oldest first (raw closes). actions: [{ex_date, kind, ...}]."""
    pts = [p for p in prices if p["trade_date"] >= start and p.get("close")]
    if len(pts) < 2:
        return None
    acts = sorted(
        (a for a in actions if a["kind"] in ORDER and pts[0]["trade_date"] < a["ex_date"] <= pts[-1]["trade_date"]),
        key=lambda a: (a["ex_date"], ORDER[a["kind"]]),
    )
    buy = pts[0]["close"]
    runs = {mode: Run(shares=amount / buy) for mode in ("price", "cash", "reinvest")}
    series, i = [], 0
    last_month = None
    for p in pts[1:]:
        while i < len(acts) and acts[i]["ex_date"] <= p["trade_date"]:
            for mode, run in runs.items():
                _apply(run, acts[i], p["close"], mode, record=(mode == "cash"))
            i += 1
        month = p["trade_date"].strftime("%Y-%m")
        if month != last_month:
            series.append({"time": p["trade_date"].isoformat(),
                           **{m: round(r.shares * p["close"] + r.cash, 2) for m, r in runs.items()}})
            last_month = month

    end = pts[-1]
    years = (end["trade_date"] - pts[0]["trade_date"]).days / 365.25

    def summary(run: Run) -> dict:
        value = run.shares * end["close"] + run.cash
        return {
            "shares": round(run.shares, 4),
            "market_value": round(run.shares * end["close"], 2),
            "cash_dividends": round(run.cash, 2),
            "total_value": round(value, 2),
            "gain_pct": round((value / amount - 1) * 100, 2),
            "cagr": round(((value / amount) ** (1 / years) - 1) * 100, 2) if years >= 1 and value > 0 else None,
        }

    cash = runs["cash"]
    demergers = [a["ex_date"].isoformat() for a in actions
                 if a["kind"] == "demerger" and pts[0]["trade_date"] < a["ex_date"] <= end["trade_date"]]
    return {
        "amount": amount,
        "start_date": pts[0]["trade_date"].isoformat(),
        "end_date": end["trade_date"].isoformat(),
        "years": round(years, 2),
        "buy_price": buy,
        "end_price": end["close"],
        "initial_shares": round(amount / buy, 4),
        "bonus_split_shares": round(runs["price"].shares - amount / buy, 4),
        "dividends_received": round(cash.cash, 2),
        "dividend_payments": sum(1 for e in cash.events if e["kind"] == "dividend"),
        "price_only": summary(runs["price"]),
        "with_dividends": summary(cash),
        "reinvested": summary(runs["reinvest"]),
        "events": cash.events,
        "series": series,
        "caveats": [f"Demerger on {d}: shares received in the new company are not included." for d in demergers],
    }
