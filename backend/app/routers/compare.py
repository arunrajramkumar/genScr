from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.cache import cached
from app.db import get_conn
from app.routers.stocks import _actions, normalize_symbol
from app.services import compare as svc
from app.services.adjust import adjust
from app.services.screener import FIELDS

router = APIRouter(tags=["compare"])

BENCHMARK = "Nifty 50"


@router.get("/compare")
@cached(maxsize=200)
def compare(
    symbols: str = Query(..., max_length=120, description="Comma-separated, 2 to 5 symbols"),
    years: int = Query(1, ge=1, le=5, description="Window for the chart and risk figures"),
    conn=Depends(get_conn),
):
    syms = list(dict.fromkeys(normalize_symbol(s) for s in symbols.split(",") if s.strip()))
    if not 2 <= len(syms) <= 5:
        raise HTTPException(400, "Provide between 2 and 5 symbols")

    rows = conn.execute(
        """
        SELECT m.*, s.symbol, s.name, s.sector, s.industry
        FROM stocks s LEFT JOIN stock_metrics m USING (symbol)
        WHERE s.symbol = ANY(%s)
        """,
        (syms,),
    ).fetchall()
    by_symbol = {r["symbol"]: r for r in rows}
    missing = [s for s in syms if s not in by_symbol]
    if missing:
        raise HTTPException(404, f"Not found: {', '.join(missing)}")

    raw = defaultdict(list)
    for r in conn.execute(
        "SELECT symbol, trade_date, open, high, low, close, prev_close FROM prices WHERE symbol = ANY(%s) ORDER BY trade_date",
        (syms,),
    ):
        raw[r["symbol"]].append(r)
    bench = svc.window(
        conn.execute(
            "SELECT trade_date, close FROM index_prices WHERE index_name = %s ORDER BY trade_date", (BENCHMARK,)
        ).fetchall(),
        years,
    )
    bench_returns = svc.daily_returns(bench)

    performance, risk, returns = {}, {}, {}
    for sym in syms:
        if not raw[sym]:
            continue
        rows_w = svc.window(adjust(raw[sym], _actions(conn, sym) or None), years)
        performance[sym] = svc.rebased(rows_w, weekly=years > 1)
        risk[sym] = svc.stats(rows_w, bench_returns, years)
        returns[sym] = svc.daily_returns(rows_w)

    quarters = defaultdict(list)
    for r in conn.execute(
        """
        SELECT symbol, period_end, revenue, net_profit FROM (
          SELECT symbol, period_end, revenue, net_profit,
                 row_number() OVER (PARTITION BY symbol ORDER BY period_end DESC) AS n
          FROM fundamentals WHERE symbol = ANY(%s) AND period_type = 'Q') q
        WHERE n <= 8 ORDER BY period_end
        """,
        (syms,),
    ):
        quarters[r["symbol"]].append(
            {"period_end": r["period_end"].isoformat(), "revenue": r["revenue"], "net_profit": r["net_profit"]}
        )

    events = defaultdict(list)
    for r in conn.execute(
        "SELECT symbol, event_date, purpose FROM events WHERE symbol = ANY(%s) AND event_date >= %s ORDER BY event_date",
        (syms, date.today()),
    ):
        if len(events[r["symbol"]]) < 2:
            events[r["symbol"]].append({"date": r["event_date"].isoformat(), "purpose": r["purpose"]})

    return {
        "stocks": [by_symbol[s] for s in syms],
        "fields": FIELDS,
        "years": years,
        "performance": performance,
        "benchmark": {"name": BENCHMARK, "performance": svc.rebased(bench, weekly=years > 1)},
        "risk": risk,
        "correlations": svc.correlations(returns),
        "quarters": quarters,
        "events": events,
    }
