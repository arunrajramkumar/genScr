from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

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
def run_screen(req: ScreenRequest, conn=Depends(get_conn)):
    try:
        filters = [f.model_dump() for f in req.filters]
        if req.query:
            filters += screener.parse_query(req.query)
        sql, params = screener.build_sql(filters, req.sector, req.sort, req.order, req.limit)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    rows = conn.execute(sql, params).fetchall()
    return {"filters": filters, "count": len(rows), "results": rows}


@router.get("/fields")
def fields():
    return screener.FIELDS


@router.get("/presets")
def presets():
    return screener.PRESETS
