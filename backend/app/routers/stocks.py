import re
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_conn
from app.services.adjust import adjust

router = APIRouter(prefix="/stocks", tags=["stocks"])

_SYMBOL = re.compile(r"^[A-Z0-9&\-]{1,20}$")
_RANGES = {"1m": 31, "6m": 183, "1y": 366, "3y": 3 * 366, "5y": 5 * 366, "max": 50 * 366}


def normalize_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not _SYMBOL.match(symbol):
        raise HTTPException(400, "Invalid symbol")
    return symbol


@router.get("/{symbol}")
def get_stock(symbol: str, conn=Depends(get_conn)):
    symbol = normalize_symbol(symbol)
    row = conn.execute(
        """
        SELECT m.*, s.*
        FROM stocks s LEFT JOIN stock_metrics m USING (symbol)
        WHERE s.symbol = %s
        """,
        (symbol,),
    ).fetchone()
    if not row:
        raise HTTPException(404, f"{symbol} not found")
    return row


@router.get("/{symbol}/prices")
def get_prices(
    symbol: str,
    range: Literal["1m", "6m", "1y", "3y", "5y", "max"] = "1y",
    conn=Depends(get_conn),
):
    symbol = normalize_symbol(symbol)
    since = date.today() - timedelta(days=_RANGES[range])
    rows = conn.execute(
        """
        SELECT trade_date, open, high, low, close, prev_close, volume
        FROM prices WHERE symbol = %s AND trade_date >= %s
        ORDER BY trade_date
        """,
        (symbol, since),
    ).fetchall()
    rows = adjust([{k: float(v) if k in ("open", "high", "low", "close", "prev_close") and v is not None else v
                    for k, v in r.items()} for r in rows])
    return [
        {"time": r["trade_date"].isoformat(), **{k: round(r[k], 2) if r[k] is not None else None
                                               for k in ("open", "high", "low", "close")}, "volume": r["volume"]}
        for r in rows
    ]


@router.get("/{symbol}/fundamentals")
def get_fundamentals(
    symbol: str,
    period: Literal["FY", "Q"] = "FY",
    limit: int = Query(10, ge=1, le=40),
    conn=Depends(get_conn),
):
    symbol = normalize_symbol(symbol)
    return conn.execute(
        """
        SELECT * FROM fundamentals
        WHERE symbol = %s AND period_type = %s
        ORDER BY period_end DESC LIMIT %s
        """,
        (symbol, period, limit),
    ).fetchall()


@router.get("/{symbol}/peers")
def get_peers(symbol: str, limit: int = Query(8, ge=1, le=20), conn=Depends(get_conn)):
    symbol = normalize_symbol(symbol)
    return conn.execute(
        """
        SELECT s.symbol, s.name, m.close, m.change_pct, m.market_cap, m.pe, m.roe, m.roce, m.return_1y
        FROM stocks s JOIN stock_metrics m USING (symbol)
        WHERE s.sector = (SELECT sector FROM stocks WHERE symbol = %s) AND s.symbol <> %s
        ORDER BY m.market_cap DESC NULLS LAST
        LIMIT %s
        """,
        (symbol, symbol, limit),
    ).fetchall()
