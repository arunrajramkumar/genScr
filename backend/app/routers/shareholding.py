import psycopg
from fastapi import APIRouter, Depends

from app.cache import cached
from app.db import get_conn
from app.routers.stocks import normalize_symbol

router = APIRouter(prefix="/stocks", tags=["shareholding"])


@router.get("/{symbol}/shareholding")
@cached(maxsize=512)
def get_shareholding(symbol: str, conn=Depends(get_conn)):
    """Last 12 filed quarters, oldest first. Percentages of total shares; fii/dii/mf are null when not filed."""
    symbol = normalize_symbol(symbol)
    try:
        return conn.execute(
            """
            SELECT period_end, promoter_pct, public_pct, fii_pct, dii_pct, mf_pct, pledged_pct
            FROM (
                SELECT * FROM shareholding WHERE symbol = %s ORDER BY period_end DESC LIMIT 12
            ) t
            ORDER BY period_end
            """,
            (symbol,),
        ).fetchall()
    except psycopg.errors.UndefinedTable:  # schema migration not applied yet: behave as "no data"
        conn.rollback()
        return []
