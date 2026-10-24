from fastapi import APIRouter, Depends, Query

from app.cache import cached
from app.db import get_conn

router = APIRouter(tags=["search"])


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/search")
@cached(maxsize=1024)
def search(
    q: str = Query(..., min_length=1, max_length=50),
    limit: int = Query(10, ge=1, le=25),
    conn=Depends(get_conn),
):
    q = q.strip()
    esc = _escape_like(q)
    # Ranked: exact symbol, former symbol (ZOMATO -> ETERNAL), then names/symbols starting with the term,
    # then a word inside the name starting with it, then fuzzy matches; bigger companies first within each tier.
    return conn.execute(
        """
        WITH renamed AS (SELECT new_symbol FROM symbol_changes WHERE upper(old_symbol) = upper(%(q)s))
        SELECT s.symbol, s.name, s.sector, m.close, m.change_pct, m.market_cap
        FROM stocks s LEFT JOIN stock_metrics m USING (symbol)
        WHERE s.symbol ILIKE %(prefix)s
           OR s.name ILIKE %(contains)s
           OR s.symbol IN (SELECT new_symbol FROM renamed)
           OR similarity(s.name, %(q)s) > 0.3
        ORDER BY CASE
                   WHEN upper(s.symbol) = upper(%(q)s) THEN 0
                   WHEN s.symbol IN (SELECT new_symbol FROM renamed) THEN 1
                   WHEN s.name ILIKE %(prefix)s OR s.symbol ILIKE %(prefix)s THEN 2
                   WHEN s.name ILIKE %(word)s THEN 3
                   ELSE 4
                 END,
                 (m.symbol IS NULL),
                 m.market_cap DESC NULLS LAST,
                 similarity(s.name, %(q)s) DESC
        LIMIT %(limit)s
        """,
        {"q": q, "prefix": f"{esc}%", "contains": f"%{esc}%", "word": f"% {esc}%", "limit": limit},
    ).fetchall()


BROWSE_LIMIT = 600
DIGITS = "0-9"


def browse_sql(letter: str, by: str) -> tuple[str, dict]:
    """Stocks whose name (or symbol) starts with `letter` ("0-9" = any digit), alphabetical."""
    col = "s.symbol" if by == "symbol" else "s.name"
    cond = f"{col} ~ '^[0-9]'" if letter == DIGITS else f"upper({col}) LIKE %(prefix)s"
    sql = (
        "SELECT s.symbol, s.name, s.sector, m.close, m.change_pct, m.market_cap "
        "FROM stocks s LEFT JOIN stock_metrics m USING (symbol) "
        f"WHERE {cond} ORDER BY upper({col}), s.symbol LIMIT %(limit)s"
    )
    return sql, {"prefix": f"{letter}%", "limit": BROWSE_LIMIT}


def letter_counts_sql(by: str) -> str:
    col = "s.symbol" if by == "symbol" else "s.name"
    return (
        f"SELECT CASE WHEN {col} ~ '^[0-9]' THEN '{DIGITS}' ELSE upper(left({col}, 1)) END AS letter, count(*) AS n "
        "FROM stocks s GROUP BY 1 ORDER BY 1"
    )


@router.get("/stocks/browse")
@cached(maxsize=64)
def browse(
    letter: str = Query("A", pattern=r"^([A-Z]|0-9)$", description="A to Z, or 0-9"),
    by: str = Query("name", pattern=r"^(name|symbol)$"),
    conn=Depends(get_conn),
):
    """A-Z directory of listed companies."""
    sql, params = browse_sql(letter, by)
    rows = conn.execute(sql, params).fetchall()
    counts = {r["letter"]: r["n"] for r in conn.execute(letter_counts_sql(by))}
    return {"letter": letter, "by": by, "stocks": rows, "truncated": len(rows) >= BROWSE_LIMIT, "letters": counts}
