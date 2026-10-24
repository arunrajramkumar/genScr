"""Rebuild the `stock_metrics` snapshot from prices + fundamentals.

    python -m app.ingest.compute_metrics
"""

from collections import defaultdict
from decimal import Decimal
from itertools import groupby

from app.db import connect
from app.services.adjust import adjust
from app.services.indicators import pct_return, rsi, sma
from app.services.scores import fundamental_ratios

COLUMNS = [
    "symbol", "as_of", "close", "change_pct", "high_52w", "low_52w", "pct_from_52w_high",
    "return_1m", "return_1y", "avg_volume_20d", "turnover", "rsi_14", "sma_50", "sma_200",
    "market_cap", "pe", "pb", "roe", "roce", "debt_to_equity", "net_margin",
    "revenue_growth_yoy", "profit_growth_yoy", "piotroski_f", "altman_z", "dividend_yield",
]

UPSERT = f"""
INSERT INTO stock_metrics ({", ".join(COLUMNS)}, updated_at)
VALUES ({", ".join(f"%({c})s" for c in COLUMNS)}, now())
ON CONFLICT (symbol) DO UPDATE SET
    {", ".join(f"{c} = EXCLUDED.{c}" for c in COLUMNS[1:])}, updated_at = now()
"""


def _f(v):
    return float(v) if isinstance(v, Decimal) else v


def _round(v, nd=2):
    return round(v, nd) if isinstance(v, float) else v


def price_metrics(rows: list[dict]) -> dict:
    closes = [_f(r["close"]) for r in rows if r["close"] is not None]
    last = rows[-1]
    year = rows[-252:]
    highs = [_f(r["high"]) for r in year if r["high"] is not None]
    lows = [_f(r["low"]) for r in year if r["low"] is not None]
    close = closes[-1] if closes else None
    prev = _f(last["prev_close"]) or (closes[-2] if len(closes) > 1 else None)
    high_52w = max(highs) if highs else None
    vols = [r["volume"] or 0 for r in rows[-20:]]
    return {
        "close": close,
        "change_pct": (close / prev - 1) * 100 if close and prev else None,
        "high_52w": high_52w,
        "low_52w": min(lows) if lows else None,
        "pct_from_52w_high": (close / high_52w - 1) * 100 if close and high_52w else None,
        "return_1m": pct_return(closes, 21),
        "return_1y": pct_return(closes, 252),
        "avg_volume_20d": int(sum(vols) / len(vols)) if vols else None,
        "turnover": _f(last["turnover"]) / 1e7 if last["turnover"] is not None else None,
        "rsi_14": rsi(closes, 14),
        "sma_50": sma(closes, 50),
        "sma_200": sma(closes, 200),
    }


def run() -> int:
    with connect() as conn:
        as_of = conn.execute("SELECT max(trade_date) AS d FROM prices").fetchone()["d"]
        if as_of is None:
            print("No prices loaded yet. Run app.ingest.bhavcopy first.")
            return 0

        funds = defaultdict(list)
        for r in conn.execute(
            """
            SELECT * FROM (
                SELECT f.*, row_number() OVER (PARTITION BY symbol ORDER BY period_end DESC) AS rn
                FROM fundamentals f WHERE period_type = 'FY'
            ) t WHERE rn <= 2 ORDER BY symbol, rn
            """
        ):
            funds[r["symbol"]].append({k: _f(v) for k, v in r.items()})

        actions = defaultdict(list)
        if conn.execute("SELECT to_regclass('public.corporate_actions') AS t").fetchone()["t"]:
            for r in conn.execute("SELECT symbol, ex_date, kind, ratio_new, ratio_held, old_fv, new_fv FROM corporate_actions "
                                  "WHERE kind IN ('bonus', 'split')"):
                actions[r["symbol"]].append(r)

        prices = conn.execute(
            """
            SELECT symbol, trade_date, close, prev_close, high, low, volume, turnover
            FROM prices WHERE trade_date > %s::date - 400
            ORDER BY symbol, trade_date
            """,
            (as_of,),
        ).fetchall()

        out = []
        for symbol, group in groupby(prices, key=lambda r: r["symbol"]):
            rows = adjust([{k: _f(v) for k, v in r.items()} for r in group], actions.get(symbol) or None)
            if rows[-1]["trade_date"] != as_of:
                continue  # not traded on the latest day (suspended / delisted)
            m = {"symbol": symbol, "as_of": as_of, **price_metrics(rows)}
            f = funds.get(symbol, [])
            m.update(fundamental_ratios(f[0] if f else None, f[1] if len(f) > 1 else None, m["close"]))
            out.append({k: _round(v) for k, v in m.items()})

        with conn.cursor() as cur:
            cur.executemany(UPSERT, out)
        conn.commit()
    print(f"stock_metrics: {len(out)} rows as of {as_of}")
    return len(out)


if __name__ == "__main__":
    run()
