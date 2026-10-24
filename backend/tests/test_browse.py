import pytest
from fastapi.testclient import TestClient

from app.db import get_conn
from app.main import ROUTERS, app
from app.routers import search, stocks
from app.routers.search import BROWSE_LIMIT, browse_sql, letter_counts_sql

client = TestClient(app)  # no lifespan (no DB pool)


def test_browse_letter_uses_parameterised_prefix():
    sql, params = browse_sql("A", "name")
    assert "upper(s.name) LIKE %(prefix)s" in sql and params == {"prefix": "A%", "limit": BROWSE_LIMIT}
    assert "ORDER BY upper(s.name)" in sql


def test_browse_digits_and_symbol_mode():
    sql, _ = browse_sql("0-9", "symbol")
    assert "s.symbol ~ '^[0-9]'" in sql and "ORDER BY upper(s.symbol)" in sql
    assert "s.symbol" in letter_counts_sql("symbol") and "s.name" in letter_counts_sql("name")


@pytest.mark.parametrize("query", ["letter=AB", "letter=a", "letter=%25", "letter=A&by=sector", "letter=1"])
def test_browse_rejects_bad_input(query):
    app.dependency_overrides[get_conn] = lambda: None
    try:
        assert client.get(f"/api/stocks/browse?{query}").status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_browse_route_registered_before_symbol_catch_all():
    assert ROUTERS.index(search) < ROUTERS.index(stocks)
