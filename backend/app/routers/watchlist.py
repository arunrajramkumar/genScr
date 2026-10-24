from fastapi import APIRouter, Depends, HTTPException, Query

from app.cache import cached
from app.db import get_conn
from app.routers.stocks import normalize_symbol

router = APIRouter(prefix="/stocks", tags=["watchlist"])

MAX_BATCH = 50


@router.get("/batch")
@cached(maxsize=256)
def batch(
    symbols: str = Query(..., max_length=1200, description="Comma-separated, 1 to 50 symbols"),
    conn=Depends(get_conn),
):
    """Summary rows for many stocks in one request (the no-login watchlist page)."""
    syms = list(dict.fromkeys(normalize_symbol(s) for s in symbols.split(",") if s.strip()))
    if not 1 <= len(syms) <= MAX_BATCH:
        raise HTTPException(400, f"Provide between 1 and {MAX_BATCH} symbols")

    rows = conn.execute(
        """
        SELECT s.symbol, s.name, m.as_of, m.close, m.change_pct, m.return_1y, m.pe,
               m.dividend_yield, m.pct_from_52w_high
        FROM stocks s LEFT JOIN stock_metrics m USING (symbol)
        WHERE s.symbol = ANY(%s)
        """,
        (syms,),
    ).fetchall()
    by_symbol = {r["symbol"]: r for r in rows}
    return {
        "stocks": [by_symbol[s] for s in syms if s in by_symbol],
        "missing": [s for s in syms if s not in by_symbol],
    }
