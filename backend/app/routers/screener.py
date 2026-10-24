from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.cache import cached
from app.db import get_conn
from app.services import screener

router = APIRouter(prefix="/screener", tags=["screener"])


class Filter(BaseModel):
    field: str
    op: str
    value: float


class ScreenRequest(BaseModel):
    query: str | None = Field(None, max_length=1000)
    filters: list[Filter] = []
    sector: str | None = None
    sort: str = "market_cap"
    order: Literal["asc", "desc"] = "desc"
    limit: int = Field(100, ge=1, le=500)


@router.post("")
@cached(maxsize=300, max_age=0)
def run_screen(req: ScreenRequest, conn=Depends(get_conn)):
    try:
        filters = [f.model_dump() for f in req.filters]
        if req.query:
            filters += screener.parse_query(req.query)
        sql, params = screener.build_sql(filters, req.sector, req.sort, req.order, req.limit)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    rows = conn.execute(sql, params).fetchall()
    total = rows[0]["total_matches"] if rows else 0
    for r in rows:
        r.pop("total_matches", None)
    universe = conn.execute("SELECT count(*) AS n FROM stock_metrics").fetchone()["n"]
    return {"filters": filters, "count": len(rows), "total": total, "universe": universe, "results": rows}


@router.get("/stats")
@cached(maxsize=4, max_age=3600)
def stats(conn=Depends(get_conn)):
    """Market distribution per field (percentiles + histogram) for the filter builder."""
    cols = list(screener.FIELDS)
    select = ", ".join("m." + c for c in cols)
    rows = conn.execute(f"SELECT s.sector, {select} FROM stock_metrics m JOIN stocks s USING (symbol)").fetchall()
    out = {}
    for c in cols:
        out[c] = screener.distribution([r[c] for r in rows if r[c] is not None])
    sectors = sorted({r["sector"] for r in rows if r["sector"]})
    return {"fields": out, "sectors": sectors, "universe": len(rows)}


@router.get("/fields")
@cached(ttl=86400, maxsize=1, max_age=86400)
def fields():
    return {k: {**v, "description": screener.DESCRIPTIONS.get(k, ""),
                "group": next((g for g, fs in screener.GROUPS.items() if k in fs), "Other")}
            for k, v in screener.FIELDS.items()}


@router.get("/presets")
@cached(ttl=86400, maxsize=1, max_age=86400)
def presets():
    return screener.PRESETS
