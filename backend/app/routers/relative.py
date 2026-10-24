from fastapi import APIRouter, Depends, HTTPException, Query

from app.cache import cached
from app.db import get_conn
from app.routers.indices import _by_slug
from app.routers.stocks import _actions, _raw_prices, normalize_symbol
from app.services.adjust import adjust
from app.services.indices import summarize
from app.services.relative import compare_to_index

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/{symbol}/vs-index")
@cached(maxsize=512)
def stock_vs_index(
    symbol: str,
    index: str = Query("nifty-50", max_length=60, pattern=r"^[a-z0-9-]+$", description="Index slug, e.g. nifty-500"),
    years: int = Query(5, ge=1, le=10),
    conn=Depends(get_conn),
):
    symbol = normalize_symbol(symbol)
    raw = _raw_prices(conn, symbol)
    if not raw:
        raise HTTPException(404, f"No prices for {symbol}")
    name, idx_rows = _by_slug(conn, index)
    stock = [{"trade_date": r["trade_date"], "close": r["close"]} for r in adjust(raw, _actions(conn, symbol) or None)]
    result = compare_to_index(stock, idx_rows, years)
    if result is None:
        raise HTTPException(404, "Not enough overlapping history")
    s = summarize(name, idx_rows)
    result["index"] = {"name": name, "slug": index, "pe": s["pe"], "pb": s["pb"], "div_yield": s["div_yield"]} if s else None
    return result
