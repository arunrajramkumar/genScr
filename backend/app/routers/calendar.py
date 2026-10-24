import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from app.cache import cached
from app.db import get_conn
from app.ingest.events import CATEGORIES

router = APIRouter(prefix="/calendar", tags=["calendar"])

KINDS = ("dividend", "bonus", "split", "rights", "buyback", "demerger")

# One round trip for the whole calendar. The anchor is the latest data date (stock_metrics.as_of),
# so the window follows the data rather than the server clock. Without corporate_actions rows the
# LEFT JOIN still returns the anchor, so the page can show its date.
_SQL = """
SELECT an.d AS as_of, a.symbol, s.name, s.sector, a.kind, a.ex_date, a.record_date,
       a.amount, a.ratio_new, a.ratio_held, a.old_fv, a.new_fv, a.price,
       m.close, m.dividend_yield,
       -- skipped when a bonus/split since the ex-date makes the current price not comparable with the amount
       CASE WHEN a.kind = 'dividend' AND NOT EXISTS (
                SELECT 1 FROM corporate_actions x WHERE x.symbol = a.symbol AND x.kind IN ('bonus', 'split')
                  AND x.ex_date > a.ex_date AND x.ex_date <= an.d)
            THEN ROUND(a.amount / NULLIF(m.close, 0) * 100, 2) END AS amount_pct
FROM (SELECT max(as_of) AS d FROM stock_metrics) an
LEFT JOIN corporate_actions a
       ON a.ex_date BETWEEN an.d - %(back)s AND an.d + %(ahead)s
      AND (%(kinds)s::text[] IS NULL OR a.kind = ANY(%(kinds)s::text[]))
LEFT JOIN stocks s ON s.symbol = a.symbol
LEFT JOIN stock_metrics m ON m.symbol = a.symbol
"""

# Board meetings and results dates (app.ingest.events). Same anchor as the corporate actions calendar.
_EVENTS_SQL = """
SELECT an.d AS as_of, e.symbol, s.name, e.event_date, e.purpose AS category, e.description
FROM (SELECT max(as_of) AS d FROM stock_metrics) an
LEFT JOIN events e
       ON e.event_date BETWEEN an.d - %(back)s AND an.d + %(ahead)s
      AND (%(categories)s::text[] IS NULL OR e.purpose = ANY(%(categories)s::text[]))
      AND (%(symbol)s::text IS NULL OR e.symbol = %(symbol)s::text)
LEFT JOIN stocks s ON s.symbol = e.symbol
"""


def _parse_choices(raw: str | None, allowed: tuple[str, ...], label: str) -> list[str] | None:
    """'dividend,bonus' -> ['dividend', 'bonus']. Blank means every choice."""
    if not raw or not raw.strip():
        return None
    items = [k.strip().lower() for k in raw.split(",") if k.strip()]
    unknown = sorted(set(items) - set(allowed))
    if unknown:
        raise HTTPException(400, f"Unknown {label}: {', '.join(unknown)}")
    return list(dict.fromkeys(items))


def parse_kinds(raw: str | None) -> list[str] | None:
    return _parse_choices(raw, KINDS, "kind")


def parse_categories(raw: str | None) -> list[str] | None:
    return _parse_choices(raw, CATEGORIES, "category")


@router.get("")
@cached(maxsize=32)
def get_calendar(
    days_back: int = Query(30, ge=0, le=365, description="Days before the latest data date"),
    days_ahead: int = Query(60, ge=0, le=365, description="Days after the latest data date"),
    kind: str | None = Query(None, description="Comma-separated: dividend, bonus, split, rights, buyback, demerger"),
    conn=Depends(get_conn),
):
    kinds = parse_kinds(kind)
    try:
        rows = conn.execute(_SQL, {"back": days_back, "ahead": days_ahead, "kinds": kinds}).fetchall()
    except psycopg.errors.UndefinedTable:  # schema migration not applied yet: behave as "no actions"
        conn.rollback()
        return {"as_of": None, "upcoming": [], "recent": []}
    as_of = rows[0]["as_of"] if rows else None
    items = [{k: v for k, v in r.items() if k != "as_of"} for r in rows if r["symbol"] is not None]
    if as_of is None:
        return {"as_of": None, "upcoming": [], "recent": []}
    upcoming = sorted((r for r in items if r["ex_date"] >= as_of), key=lambda r: (r["ex_date"], r["symbol"]))
    recent = sorted((r for r in items if r["ex_date"] < as_of), key=lambda r: (-r["ex_date"].toordinal(), r["symbol"]))
    return {"as_of": as_of, "upcoming": upcoming, "recent": recent}


@router.get("/events")
@cached(maxsize=256)
def get_events(
    symbol: str | None = Query(None, max_length=20, description="One company, e.g. TCS"),
    category: str | None = Query(None, description="Comma-separated: results, dividend, fund_raising, other"),
    days_back: int = Query(30, ge=0, le=365, description="Days before the latest data date"),
    days_ahead: int = Query(90, ge=0, le=365, description="Days after the latest data date"),
    conn=Depends(get_conn),
):
    categories = parse_categories(category)
    symbol = symbol.strip().upper() if symbol and symbol.strip() else None
    empty = {"as_of": None, "upcoming": [], "recent": []}
    try:
        rows = conn.execute(
            _EVENTS_SQL,
            {"back": days_back, "ahead": days_ahead, "categories": categories, "symbol": symbol},
        ).fetchall()
    except psycopg.errors.UndefinedTable:  # schema migration not applied yet: behave as "no events"
        conn.rollback()
        return empty
    as_of = rows[0]["as_of"] if rows else None
    if as_of is None:
        return empty
    items = [{k: v for k, v in r.items() if k != "as_of"} for r in rows if r["symbol"] is not None]
    upcoming = sorted((r for r in items if r["event_date"] >= as_of), key=lambda r: (r["event_date"], r["symbol"], r["category"]))
    recent = sorted((r for r in items if r["event_date"] < as_of),
                    key=lambda r: (-r["event_date"].toordinal(), r["symbol"], r["category"]))
    return {"as_of": as_of, "upcoming": upcoming, "recent": recent}
