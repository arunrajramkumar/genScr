from collections import defaultdict
from datetime import date

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from app.cache import cached
from app.db import get_conn
from app.services.indices import rebased, slugify, summarize, weekly
from app.services.risk import risk_profile

router = APIRouter(prefix="/indices", tags=["indices"])

COLS = "index_name, trade_date, close, change_pct, pe, pb, div_yield"


def _all(conn) -> dict[str, list[dict]]:
    try:
        rows = conn.execute(f"SELECT {COLS} FROM index_prices ORDER BY index_name, trade_date").fetchall()
    except psycopg.errors.UndefinedTable:
        conn.rollback()
        return {}
    out: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        out[r["index_name"]].append(r)
    return out


def _by_slug(conn, slug: str) -> tuple[str, list[dict]]:
    names = {slugify(r["index_name"]): r["index_name"] for r in conn.execute("SELECT DISTINCT index_name FROM index_prices")}
    name = names.get(slug)
    if not name:
        raise HTTPException(404, "Index not found")
    rows = conn.execute(f"SELECT {COLS} FROM index_prices WHERE index_name = %s ORDER BY trade_date", (name,)).fetchall()
    return name, rows


@router.get("")
@cached(maxsize=2)
def list_indices(conn=Depends(get_conn)):
    items = [s for name, rows in _all(conn).items() if (s := summarize(name, rows))]
    latest = max((i["as_of"] for i in items), default=None)
    items = [i for i in items if i["as_of"] == latest]  # drop discontinued indices
    return sorted(items, key=lambda i: (i["category"] != "Broad market", i["name"]))


@router.get("/compare")
@cached(maxsize=200)
def compare_indices(slugs: str = Query(..., description="Comma-separated index slugs, 2 to 6"),
                    years: int = Query(1, ge=1, le=10), conn=Depends(get_conn)):
    wanted = list(dict.fromkeys(s.strip() for s in slugs.split(",") if s.strip()))
    if not 2 <= len(wanted) <= 6:
        raise HTTPException(400, "Provide between 2 and 6 indices")
    out = []
    for slug in wanted:
        name, rows = _by_slug(conn, slug)
        end = rows[-1]["trade_date"]
        start = date(end.year - years, end.month, min(end.day, 28))
        out.append({"summary": summarize(name, rows), "series": rebased(rows, start)})
    return out


@router.get("/{slug}")
@cached(maxsize=200)
def get_index(slug: str, conn=Depends(get_conn)):
    name, rows = _by_slug(conn, slug)
    members = conn.execute(
        """
        SELECT s.symbol, s.name, s.sector, m.close, m.change_pct, m.market_cap, m.pe, m.roe, m.return_1y, m.dividend_yield
        FROM index_constituents c JOIN stocks s USING (symbol) LEFT JOIN stock_metrics m USING (symbol)
        WHERE c.index_name = %s ORDER BY m.market_cap DESC NULLS LAST
        """,
        (name,),
    ).fetchall()
    sectors: dict[str, int] = defaultdict(int)
    for m in members:
        sectors[m["sector"] or "Other"] += 1
    risk = risk_profile([{"trade_date": r["trade_date"], "close": r["close"]} for r in rows])
    return {
        "summary": summarize(name, rows),
        "prices": [{"time": r["trade_date"].isoformat(), "value": r["close"]} for r in rows],
        "valuation": weekly(rows, ("pe", "pb", "div_yield")),
        "risk": risk,
        "constituents": members,
        "sector_mix": sorted(sectors.items(), key=lambda kv: -kv[1]),
    }
