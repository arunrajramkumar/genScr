import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.cache import cached
from app.db import get_conn

router = APIRouter(prefix="/market", tags=["market"])

# Heatmap period -> stock_metrics column. No 1-week return column exists, so 1w is not offered.
HEATMAP_COLUMNS = {"1d": "change_pct", "1m": "return_1m", "1y": "return_1y"}
HEATMAP_LIMIT = 500
# Sanity ceiling in ₹ crore (about 6x Reliance). Drops bad share-count data, e.g. FIVESTAR at ~1.3e9 Cr.
HEATMAP_MAX_MCAP = 10_000_000

_LIST = """
    SELECT s.symbol, s.name, m.close, m.change_pct, m.turnover, m.market_cap
    FROM stock_metrics m JOIN stocks s USING (symbol)
    WHERE m.as_of = %(as_of)s AND (m.market_cap IS NULL OR m.market_cap >= 500) AND m.turnover >= 1
    ORDER BY {order} NULLS LAST LIMIT 10
"""


@router.get("/overview")
@cached(maxsize=4)
def overview(conn=Depends(get_conn)):
    as_of = conn.execute("SELECT max(as_of) AS d FROM stock_metrics").fetchone()["d"]
    if as_of is None:
        return {"as_of": None, "breadth": None, "gainers": [], "losers": [], "active": [], "sectors": []}

    p = {"as_of": as_of}
    breadth = conn.execute(
        """
        SELECT count(*) FILTER (WHERE change_pct > 0) AS advances,
               count(*) FILTER (WHERE change_pct < 0) AS declines,
               count(*) FILTER (WHERE change_pct = 0) AS unchanged,
               count(*) FILTER (WHERE close >= high_52w) AS new_highs,
               count(*) FILTER (WHERE close <= low_52w) AS new_lows
        FROM stock_metrics WHERE as_of = %(as_of)s
        """,
        p,
    ).fetchone()
    sectors = conn.execute(
        """
        SELECT s.sector, count(*) AS stocks, round(avg(m.change_pct), 2) AS avg_change,
               round(avg(m.return_1y), 2) AS avg_return_1y
        FROM stock_metrics m JOIN stocks s USING (symbol)
        WHERE m.as_of = %(as_of)s AND s.sector IS NOT NULL
        GROUP BY s.sector ORDER BY avg_change DESC
        """,
        p,
    ).fetchall()
    return {
        "as_of": as_of,
        "breadth": breadth,
        "gainers": conn.execute(_LIST.format(order="m.change_pct DESC"), p).fetchall(),
        "losers": conn.execute(_LIST.format(order="m.change_pct ASC"), p).fetchall(),
        "active": conn.execute(_LIST.format(order="m.turnover DESC"), p).fetchall(),
        "sectors": sectors,
    }


PULSE_SQL = """
SELECT count(*) AS stocks,
       count(*) FILTER (WHERE close > sma_50) AS above_50,  count(*) FILTER (WHERE sma_50 IS NOT NULL) AS has_50,
       count(*) FILTER (WHERE close > sma_200) AS above_200, count(*) FILTER (WHERE sma_200 IS NOT NULL) AS has_200,
       count(*) FILTER (WHERE rsi_14 > 70) AS rsi_above_70, count(*) FILTER (WHERE rsi_14 < 30) AS rsi_below_30,
       count(*) FILTER (WHERE rsi_14 IS NOT NULL) AS has_rsi,
       count(*) FILTER (WHERE pct_from_52w_high >= -5) AS off_0_5,
       count(*) FILTER (WHERE pct_from_52w_high < -5 AND pct_from_52w_high >= -20) AS off_5_20,
       count(*) FILTER (WHERE pct_from_52w_high < -20 AND pct_from_52w_high >= -40) AS off_20_40,
       count(*) FILTER (WHERE pct_from_52w_high < -40) AS off_40_plus,
       count(*) FILTER (WHERE return_1y > 0) AS up_1y, count(*) FILTER (WHERE return_1y IS NOT NULL) AS has_1y,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY return_1y) AS median_return_1y,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY pct_from_52w_high) AS median_from_high
FROM stock_metrics WHERE as_of = %(as_of)s
"""

PULSE_SECTORS_SQL = """
SELECT s.sector, count(*) AS stocks,
       round(100.0 * count(*) FILTER (WHERE m.close > m.sma_200) / nullif(count(m.sma_200), 0), 1) AS pct_above_200,
       round(100.0 * count(*) FILTER (WHERE m.close > m.sma_50) / nullif(count(m.sma_50), 0), 1) AS pct_above_50,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY m.pct_from_52w_high)::numeric, 1) AS median_from_high
FROM stock_metrics m JOIN stocks s USING (symbol)
WHERE m.as_of = %(as_of)s AND s.sector IS NOT NULL
GROUP BY s.sector HAVING count(*) >= 10
ORDER BY pct_above_200 DESC NULLS LAST
"""


@router.get("/pulse")
@cached(maxsize=2)
def pulse(conn=Depends(get_conn)):
    """Share of the market above its moving averages, distance from 52-week highs, by sector. Descriptive only."""
    as_of = conn.execute("SELECT max(as_of) AS d FROM stock_metrics").fetchone()["d"]
    if as_of is None:
        return {"as_of": None, "market": None, "sectors": []}
    p = {"as_of": as_of}
    market = conn.execute(PULSE_SQL, p).fetchone()
    return {"as_of": as_of, "market": market, "sectors": conn.execute(PULSE_SECTORS_SQL, p).fetchall()}


def _short_name(name: str) -> str:
    return re.sub(r"\s+(Ltd\.?|Limited)$", "", name.strip(), flags=re.IGNORECASE)


def _group_by_sector(rows: list[dict]) -> list[dict]:
    """Rows sorted by market cap desc -> sectors (largest first), each with its stocks."""
    sectors: dict[str, dict] = {}
    for r in rows:
        g = sectors.setdefault(r["sector"], {"sector": r["sector"], "market_cap": 0.0, "stocks": []})
        g["market_cap"] += r["market_cap"]
        g["stocks"].append({
            "symbol": r["symbol"],
            "name": _short_name(r["name"]),
            "market_cap": round(r["market_cap"]),
            "value": round(r["value"], 2),
        })
    out = sorted(sectors.values(), key=lambda g: g["market_cap"], reverse=True)
    for g in out:
        g["market_cap"] = round(g["market_cap"])
    return out


@router.get("/heatmap")
@cached(maxsize=32)
def heatmap(universe: str = Query("all", min_length=1, max_length=64, description="'all' or an index name, e.g. 'Nifty 50'"),
            period: Literal["1d", "1m", "1y"] = "1d", conn=Depends(get_conn)):
    col = HEATMAP_COLUMNS[period]
    as_of = conn.execute("SELECT max(as_of) AS d FROM stock_metrics").fetchone()["d"]
    if as_of is None:
        return {"as_of": None, "universe": universe, "period": period, "count": 0, "sectors": []}

    p: dict = {"as_of": as_of, "max_mcap": HEATMAP_MAX_MCAP}
    scope = ""
    if universe != "all":
        if conn.execute("SELECT 1 FROM index_constituents WHERE index_name = %s LIMIT 1", (universe,)).fetchone() is None:
            raise HTTPException(404, "Unknown universe")
        scope = "AND m.symbol IN (SELECT symbol FROM index_constituents WHERE index_name = %(index)s)"
        p["index"] = universe
    rows = conn.execute(
        f"""
        SELECT s.symbol, s.name, COALESCE(s.sector, 'Unclassified') AS sector, m.market_cap, m.{col} AS value
        FROM stock_metrics m JOIN stocks s USING (symbol)
        WHERE m.as_of = %(as_of)s AND m.market_cap BETWEEN 1 AND %(max_mcap)s AND m.{col} IS NOT NULL {scope}
        ORDER BY m.market_cap DESC LIMIT {HEATMAP_LIMIT}
        """,
        p,
    ).fetchall()
    sectors = _group_by_sector(rows)
    return {"as_of": as_of, "universe": universe, "period": period, "count": len(rows), "sectors": sectors}
