from fastapi import APIRouter, Depends, HTTPException

from app.cache import cached
from app.db import get_conn
from app.routers.stocks import _actions, _raw_prices, normalize_symbol
from app.services.valuation import valuation_history

router = APIRouter(prefix="/stocks", tags=["valuation"])


@router.get("/{symbol}/valuation")
@cached(maxsize=512)
def get_valuation(symbol: str, conn=Depends(get_conn)):
    """Weekly trailing P/E and P/B against the stock's own history (see app.services.valuation)."""
    symbol = normalize_symbol(symbol)
    rows = _raw_prices(conn, symbol)
    if not rows:
        raise HTTPException(404, f"No prices for {symbol}")
    fundamentals = conn.execute(
        "SELECT period_end, period_type, eps, total_equity, shares_outstanding FROM fundamentals WHERE symbol = %s",
        (symbol,),
    ).fetchall()
    return valuation_history(rows, fundamentals, _actions(conn, symbol))
