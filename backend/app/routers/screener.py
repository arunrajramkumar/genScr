from collections import Counter
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.cache import cached
from app.db import get_conn
from app.services import screener

router = APIRouter(prefix="/screener", tags=["screener"])


class Filter(BaseModel):
    field: str = Field(max_length=40)
    op: str = Field(max_length=2)
    value: float = Field(allow_inf_nan=False)


class ScreenRequest(BaseModel):
    query: str | None = Field(None, max_length=1000)
    filters: list[Filter] = Field([], max_length=20)
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
        isql, iparams = screener.insights_sql(filters, req.sector)
        msql, ssql, mparams = screener.matches_sql(filters, req.sector)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    rows = conn.execute(sql, params).fetchall()
    for r in rows:
        r.pop("total_matches", None)
    info = screener.insights(conn.execute(isql, iparams).fetchone(), filters, req.sector)
    total = info["funnel"][-1]["remaining"] if info["funnel"] else info["universe"]
    medians = {k: round(v, 2) for k, v in conn.execute(msql, mparams).fetchone().items() if v is not None}
    sectors = [[r["sector"], r["n"]] for r in conn.execute(ssql, mparams)]
    return {"filters": filters, "count": len(rows), "total": total, "universe": info["universe"],
            "funnel": info["funnel"], "sizes": info["sizes"], "medians": medians, "sectors": sectors, "results": rows}


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
    counts = Counter(r["sector"] for r in rows if r["sector"])
    sectors = sorted(counts)
    return {"fields": out, "sectors": sectors, "sector_counts": [[s, counts[s]] for s in sectors], "universe": len(rows)}


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
