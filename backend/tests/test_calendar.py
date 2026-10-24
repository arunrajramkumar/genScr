from datetime import date

import psycopg
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.routers.calendar import get_calendar, parse_kinds

client = TestClient(app)  # no context manager: lifespan (DB pool) is not started

ANCHOR = date(2026, 10, 23)


class FakeConn:
    """Stands in for a psycopg connection: records the calls and returns canned rows."""

    def __init__(self, rows=None, error=None):
        self.rows, self.error = rows or [], error
        self.calls, self.params, self.rolled_back = 0, None, False

    def execute(self, sql, params=None):
        self.calls += 1
        self.params = params
        if self.error:
            raise self.error
        return self

    def fetchall(self):
        return self.rows

    def rollback(self):
        self.rolled_back = True


def _row(symbol, ex_date, kind="dividend", **extra):
    base = {"as_of": ANCHOR, "symbol": symbol, "name": f"{symbol} Ltd", "sector": None, "kind": kind,
            "ex_date": ex_date, "record_date": ex_date, "amount": None, "ratio_new": None, "ratio_held": None,
            "old_fv": None, "new_fv": None, "price": None, "close": 100.0, "dividend_yield": 1.0, "amount_pct": None}
    base.update(extra)
    return base


def _calendar(conn, **kw):
    # __wrapped__ skips the response cache so each test sees its own fake connection.
    args = {"days_back": 30, "days_ahead": 60, "kind": None}
    args.update(kw)
    return get_calendar.__wrapped__(conn=conn, **args)


def test_calendar_route_is_registered():
    assert "/api/calendar" in client.get("/openapi.json").json()["paths"]


def test_parse_kinds():
    assert parse_kinds(None) is None and parse_kinds("  ") is None
    assert parse_kinds("dividend, Bonus,dividend") == ["dividend", "bonus"]
    with pytest.raises(HTTPException) as err:
        parse_kinds("dividend,nope")
    assert err.value.status_code == 400


def test_upcoming_sorted_first_then_recent_newest_first():
    rows = [
        _row("OLD1", date(2026, 10, 1)),
        _row("NEW2", date(2026, 11, 1)),
        _row("TODAY", ANCHOR),
        _row("RECENT", date(2026, 10, 20)),
        _row("NEW1", date(2026, 10, 25)),
        _row("OLD2", date(2026, 10, 10)),
    ]
    conn = FakeConn(rows)
    out = _calendar(conn)
    assert conn.calls == 1  # one query for the whole calendar, no per-row lookups
    assert out["as_of"] == ANCHOR
    assert [r["symbol"] for r in out["upcoming"]] == ["TODAY", "NEW1", "NEW2"]
    assert [r["symbol"] for r in out["recent"]] == ["RECENT", "OLD2", "OLD1"]
    assert all("as_of" not in r for r in out["upcoming"] + out["recent"])


def test_window_and_kind_are_passed_to_the_query():
    conn = FakeConn([])
    _calendar(conn, days_back=5, days_ahead=7, kind="dividend,bonus")
    assert conn.params == {"back": 5, "ahead": 7, "kinds": ["dividend", "bonus"]}
    conn = FakeConn([])
    _calendar(conn)  # default: every kind
    assert conn.params["kinds"] is None


def test_missing_table_gives_an_empty_calendar():
    conn = FakeConn(error=psycopg.errors.UndefinedTable("relation corporate_actions does not exist"))
    out = _calendar(conn)
    assert conn.rolled_back
    assert out == {"as_of": None, "upcoming": [], "recent": []}


def test_empty_stock_metrics_gives_an_empty_calendar():
    # No latest date: the anchor row has no action attached.
    conn = FakeConn([_row(None, None, kind=None, as_of=None)])
    assert _calendar(conn) == {"as_of": None, "upcoming": [], "recent": []}
