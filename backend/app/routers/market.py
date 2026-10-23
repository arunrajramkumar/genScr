from fastapi import APIRouter, Depends

from app.cache import cached
from app.db import get_conn

router = APIRouter(prefix="/market", tags=["market"])

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
