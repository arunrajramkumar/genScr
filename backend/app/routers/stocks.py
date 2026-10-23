import re
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.cache import cached
from app.db import get_conn
from app.services.adjust import adjust
from app.services.facts import build_facts

router = APIRouter(prefix="/stocks", tags=["stocks"])

_SYMBOL = re.compile(r"^[A-Z0-9&\-]{1,20}$")
_RANGES = {"1m": 31, "6m": 183, "1y": 366, "3y": 3 * 366, "5y": 5 * 366, "max": 50 * 366}


def normalize_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not _SYMBOL.match(symbol):
        raise HTTPException(400, "Invalid symbol")
    return symbol


@router.get("/{symbol}")
@cached(maxsize=512)
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
@cached(maxsize=150)  # ~130 KB each -> ~20 MB worst case
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
    rows = adjust(rows)
    return [
        {"time": r["trade_date"].isoformat(), **{k: round(r[k], 2) if r[k] is not None else None
                                               for k in ("open", "high", "low", "close")}, "volume": r["volume"]}
        for r in rows
    ]


@router.get("/{symbol}/fundamentals")
@cached(maxsize=512)
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
@cached(maxsize=512)
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


@router.get("/{symbol}/facts")
@cached(maxsize=512)
def get_facts(symbol: str, conn=Depends(get_conn)):
    symbol = normalize_symbol(symbol)
    stock = conn.execute(
        "SELECT m.*, s.* FROM stocks s LEFT JOIN stock_metrics m USING (symbol) WHERE s.symbol = %s", (symbol,)
    ).fetchone()
    if not stock:
        raise HTTPException(404, f"{symbol} not found")
    prices = conn.execute(
        "SELECT trade_date, open, high, low, close, prev_close, volume FROM prices WHERE symbol = %s ORDER BY trade_date",
        (symbol,),
    ).fetchall()
    fy = conn.execute(
        "SELECT * FROM fundamentals WHERE symbol = %s AND period_type = 'FY' ORDER BY period_end DESC LIMIT 4", (symbol,)
    ).fetchall()
    rank = conn.execute(
        """
        SELECT rank, total, sector_rank, sector_total FROM (
            SELECT m.symbol,
                   rank() OVER (ORDER BY m.market_cap DESC) AS rank,
                   count(*) OVER () AS total,
                   rank() OVER (PARTITION BY s.sector ORDER BY m.market_cap DESC) AS sector_rank,
                   count(*) OVER (PARTITION BY s.sector) AS sector_total
            FROM stock_metrics m JOIN stocks s USING (symbol)
            WHERE m.market_cap IS NOT NULL
        ) t WHERE symbol = %s
        """,
        (symbol,),
    ).fetchone()
    return build_facts(stock, prices, fy, rank)
