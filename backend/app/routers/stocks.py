import re
from datetime import date, timedelta
from typing import Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from app.cache import cached
from app.db import get_conn
from app.services.adjust import adjust
from app.services.dividends import dividend_history
from app.services.facts import build_facts
from app.services.ranks import RANKED, percentile_ranks
from app.services.risk import risk_profile
from app.services.timeline import build_timeline
from app.services.total_return import total_return

router = APIRouter(prefix="/stocks", tags=["stocks"])

_SYMBOL = re.compile(r"^[A-Z0-9&\-]{1,20}$")
_RANGES = {"1m": 31, "6m": 183, "1y": 366, "3y": 3 * 366, "5y": 5 * 366, "max": 50 * 366}


def _actions(conn, symbol: str) -> list[dict]:
    try:
        return conn.execute(
            "SELECT ex_date, kind, amount, ratio_new, ratio_held, old_fv, new_fv, price, subject "
            "FROM corporate_actions WHERE symbol = %s ORDER BY ex_date",
            (symbol,),
        ).fetchall()
    except psycopg.errors.UndefinedTable:  # schema migration not applied yet: behave as "no actions"
        conn.rollback()
        return []


def _raw_prices(conn, symbol: str) -> list[dict]:
    return conn.execute(
        "SELECT trade_date, open, high, low, close, prev_close FROM prices WHERE symbol = %s ORDER BY trade_date", (symbol,)
    ).fetchall()


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
    try:
        row["indices"] = [r["index_name"] for r in conn.execute(
            "SELECT index_name FROM index_constituents WHERE symbol = %s ORDER BY index_name", (symbol,))]
    except psycopg.errors.UndefinedTable:
        conn.rollback()
        row["indices"] = []
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
    rows = adjust(rows, _actions(conn, symbol) or None)  # None -> fall back to gap heuristic
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
    return build_facts(stock, prices, fy, rank, actions=_actions(conn, symbol) or None)


@router.get("/{symbol}/dividends")
@cached(maxsize=512)
def get_dividends(symbol: str, conn=Depends(get_conn)):
    symbol = normalize_symbol(symbol)
    return dividend_history(_actions(conn, symbol), _raw_prices(conn, symbol))


@router.get("/{symbol}/timeline")
@cached(maxsize=512)
def get_timeline(symbol: str, conn=Depends(get_conn)):
    symbol = normalize_symbol(symbol)
    stock = conn.execute("SELECT symbol, name, listing_date FROM stocks WHERE symbol = %s", (symbol,)).fetchone()
    if not stock:
        raise HTTPException(404, f"{symbol} not found")
    return build_timeline(stock, _actions(conn, symbol), _raw_prices(conn, symbol))


@router.get("/{symbol}/total-return")
@cached(maxsize=1024)
def get_total_return(
    symbol: str,
    years: int = Query(5, ge=1, le=30),
    amount: float = Query(10_000, gt=0, le=1e9),
    conn=Depends(get_conn),
):
    symbol = normalize_symbol(symbol)
    prices = _raw_prices(conn, symbol)
    if not prices:
        raise HTTPException(404, f"No prices for {symbol}")
    end = prices[-1]["trade_date"]
    start = date(end.year - years, end.month, min(end.day, 28))
    result = total_return(prices, _actions(conn, symbol), start, amount)
    if result is None:
        raise HTTPException(404, "Not enough price history for that period")
    first = prices[0]["trade_date"]
    result["available_years"] = int((end - first).days / 365.25 + 0.02)
    result["benchmark"] = _benchmark(conn, "Nifty 50", date.fromisoformat(result["start_date"]), end, amount)
    return result


def _benchmark(conn, index_name: str, start: date, end: date, amount: float) -> dict | None:
    """Same amount in the index over the same dates (price index: index dividends are not included)."""
    try:
        rows = conn.execute(
            "SELECT trade_date, close FROM index_prices "
            "WHERE index_name = %s AND trade_date BETWEEN %s AND %s ORDER BY trade_date",
            (index_name, start, end),
        ).fetchall()
    except psycopg.errors.UndefinedTable:
        conn.rollback()
        return None
    if len(rows) < 2 or rows[0]["trade_date"] > start.replace(day=min(start.day + 7, 28)):
        return None
    value = amount * rows[-1]["close"] / rows[0]["close"]
    years = (rows[-1]["trade_date"] - rows[0]["trade_date"]).days / 365.25
    return {"name": index_name, "value": round(value, 2),
            "cagr": round(((value / amount) ** (1 / years) - 1) * 100, 2) if years >= 1 else None}


@router.get("/{symbol}/risk")
@cached(maxsize=512)
def get_risk(symbol: str, conn=Depends(get_conn)):
    symbol = normalize_symbol(symbol)
    raw = _raw_prices(conn, symbol)
    if not raw:
        raise HTTPException(404, f"No prices for {symbol}")
    result = risk_profile(adjust(raw, _actions(conn, symbol) or None))
    if result is None:
        raise HTTPException(404, "Not enough price history")
    return result


@router.get("/{symbol}/ranks")
@cached(maxsize=512)
def get_ranks(symbol: str, conn=Depends(get_conn)):
    symbol = normalize_symbol(symbol)
    rows = conn.execute(
        f"SELECT m.symbol, s.sector, {', '.join('m.' + f for f in RANKED)} FROM stock_metrics m JOIN stocks s USING (symbol)"
    ).fetchall()
    return percentile_ranks(symbol, rows)
