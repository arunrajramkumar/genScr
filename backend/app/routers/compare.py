from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_conn
from app.routers.stocks import normalize_symbol
from app.services.screener import FIELDS

router = APIRouter(tags=["compare"])


@router.get("/compare")
def compare(symbols: str = Query(..., description="Comma-separated, 2 to 5 symbols"), conn=Depends(get_conn)):
    syms = list(dict.fromkeys(normalize_symbol(s) for s in symbols.split(",") if s.strip()))
    if not 2 <= len(syms) <= 5:
        raise HTTPException(400, "Provide between 2 and 5 symbols")

    rows = conn.execute(
        """
        SELECT m.*, s.symbol, s.name, s.sector
        FROM stocks s LEFT JOIN stock_metrics m USING (symbol)
        WHERE s.symbol = ANY(%s)
        """,
        (syms,),
    ).fetchall()
    by_symbol = {r["symbol"]: r for r in rows}
    missing = [s for s in syms if s not in by_symbol]
    if missing:
        raise HTTPException(404, f"Not found: {', '.join(missing)}")

    # 1-year performance rebased to 100.
    series = defaultdict(list)
    for r in conn.execute(
        "SELECT symbol, trade_date, close FROM prices WHERE symbol = ANY(%s) AND trade_date >= %s ORDER BY trade_date",
        (syms, date.today() - timedelta(days=366)),
    ):
        series[r["symbol"]].append(r)
    performance = {}
    for sym, pts in series.items():
        base = float(pts[0]["close"] or 0)
        if base:
            performance[sym] = [
                {"time": p["trade_date"].isoformat(), "value": round(float(p["close"]) / base * 100, 2)} for p in pts
            ]

    return {"stocks": [by_symbol[s] for s in syms], "fields": FIELDS, "performance": performance}
