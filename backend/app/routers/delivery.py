from fastapi import APIRouter, Depends

from app.cache import cached
from app.db import get_conn
from app.routers.stocks import normalize_symbol

router = APIRouter(prefix="/stocks", tags=["delivery"])


@router.get("/{symbol}/delivery")
@cached(maxsize=512)
def get_delivery(symbol: str, conn=Depends(get_conn)):
    """Daily delivery % (share of traded quantity taken for delivery) for the last ~250 trading days."""
    symbol = normalize_symbol(symbol)
    rows = conn.execute(
        """
        SELECT trade_date, deliv_pct FROM prices
        WHERE symbol = %s AND series IN ('EQ', 'BE') AND deliv_pct IS NOT NULL
        ORDER BY trade_date DESC LIMIT 250
        """,
        (symbol,),
    ).fetchall()
    return [{"time": r["trade_date"].isoformat(), "deliv_pct": r["deliv_pct"]} for r in reversed(rows)]
