import pytest
from fastapi.testclient import TestClient

from app.cache import clear_all
from app.db import get_conn
from app.main import app
from app.routers.watchlist import MAX_BATCH

client = TestClient(app)  # no context manager: the DB pool is not started, the dependency is overridden

ROWS = [
    {"symbol": "TCS", "name": "Tata Consultancy Services", "as_of": None, "close": 3500.0, "change_pct": 1.2,
     "return_1y": -5.0, "pe": 28.0, "dividend_yield": 1.5, "pct_from_52w_high": -10.0},
    {"symbol": "INFY", "name": "Infosys", "as_of": None, "close": 1500.0, "change_pct": -0.4,
     "return_1y": 3.0, "pe": 24.0, "dividend_yield": None, "pct_from_52w_high": -2.0},
]


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeConn:
    """Records queries; the batch query is the only one that filters by symbol (ANY)."""

    def __init__(self, rows):
        self.rows = rows
        self.batch_queries = 0

    def execute(self, sql, params=None):
        if "ANY" in sql:
            self.batch_queries += 1
            return FakeResult(self.rows)
        return FakeResult([{"v": None, "i": None}])  # cache freshness check


@pytest.fixture
def fake_db():
    conn = FakeConn(ROWS)
    app.dependency_overrides[get_conn] = lambda: conn
    clear_all()
    yield conn
    app.dependency_overrides.clear()
    clear_all()


def test_batch_is_one_query_dedupes_and_reports_missing(fake_db):
    r = client.get("/api/stocks/batch", params={"symbols": " tcs, infy ,ZZZ,tcs"})
    assert r.status_code == 200
    body = r.json()
    assert [s["symbol"] for s in body["stocks"]] == ["TCS", "INFY"]  # request order, deduplicated
    assert body["missing"] == ["ZZZ"]
    assert body["stocks"][0]["pct_from_52w_high"] == -10.0
    assert fake_db.batch_queries == 1


def test_batch_allows_up_to_50_and_rejects_more(fake_db):
    assert MAX_BATCH == 50
    ok = ",".join(f"SYM{i}" for i in range(MAX_BATCH))
    assert client.get("/api/stocks/batch", params={"symbols": ok}).status_code == 200
    too_many = ",".join(f"SYM{i}" for i in range(MAX_BATCH + 1))
    assert client.get("/api/stocks/batch", params={"symbols": too_many}).status_code == 400


@pytest.mark.parametrize("bad", ["", " , ", "TCS;DROP TABLE stocks", "TCS,<script>"])
def test_batch_rejects_empty_or_invalid_symbols(fake_db, bad):
    assert client.get("/api/stocks/batch", params={"symbols": bad}).status_code == 400
