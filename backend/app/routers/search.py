from fastapi import APIRouter, Depends, Query

from app.db import get_conn

router = APIRouter(tags=["search"])


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/search")
def search(
    q: str = Query(..., min_length=1, max_length=50),
    limit: int = Query(10, ge=1, le=25),
    conn=Depends(get_conn),
):
    q = q.strip()
    esc = _escape_like(q)
    return conn.execute(
        """
        SELECT s.symbol, s.name, s.sector, m.close, m.change_pct, m.market_cap
        FROM stocks s LEFT JOIN stock_metrics m USING (symbol)
        WHERE s.symbol ILIKE %(prefix)s
           OR s.name ILIKE %(contains)s
           OR similarity(s.name, %(q)s) > 0.3
        ORDER BY (upper(s.symbol) = upper(%(q)s)) DESC,
                 (s.symbol ILIKE %(prefix)s) DESC,
                 similarity(s.name, %(q)s) DESC,
                 m.market_cap DESC NULLS LAST
        LIMIT %(limit)s
        """,
        {"q": q, "prefix": f"{esc}%", "contains": f"%{esc}%", "limit": limit},
    ).fetchall()
