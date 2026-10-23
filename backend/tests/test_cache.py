from datetime import date

import orjson
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

import app.cache as cache_mod
from app.cache import TTLCache, cached, dumps, ensure_fresh


def test_ttl_expiry_and_lru_eviction():
    c = TTLCache(ttl=10, maxsize=2)
    c.set("a", 1, now=0)
    c.set("b", 2, now=0)
    assert c.get("a", now=5) == 1  # touch a -> b is least recently used
    c.set("c", 3, now=5)
    assert c.get("b", now=5) is None and len(c) == 2
    assert c.get("a", now=10) is None  # expired


def test_dumps_handles_dates_and_decimals():
    from decimal import Decimal

    assert orjson.loads(dumps({"d": date(2026, 10, 23), "x": Decimal("1.5")})) == {"d": "2026-10-23", "x": 1.5}


class Body(BaseModel):
    q: str


@pytest.fixture
def api():
    calls = {"n": 0}
    app = FastAPI()

    @app.get("/item/{item_id}")
    @cached(maxsize=10, max_age=120)
    def item(item_id: str, flag: int = 0):
        calls["n"] += 1
        if item_id == "missing":
            raise HTTPException(404, "nope")
        return {"id": item_id, "flag": flag, "when": date(2026, 1, 1)}

    @app.post("/search")
    @cached(maxsize=10, max_age=0)
    def search(body: Body):
        calls["n"] += 1
        return {"q": body.q}

    return TestClient(app), calls


def test_cached_route_computes_once_per_arguments(api):
    client, calls = api
    r1 = client.get("/item/a")
    r2 = client.get("/item/a")
    assert r1.json() == r2.json() == {"id": "a", "flag": 0, "when": "2026-01-01"}
    assert calls["n"] == 1
    assert r1.headers["cache-control"] == "public, max-age=120, stale-while-revalidate=3600"
    client.get("/item/a?flag=1")
    assert calls["n"] == 2  # different arguments -> different entry


def test_cached_route_never_caches_errors(api):
    client, calls = api
    assert client.get("/item/missing").status_code == 404
    assert client.get("/item/missing").status_code == 404
    assert calls["n"] == 2


def test_cached_post_body_is_part_of_key(api):
    client, calls = api
    assert client.post("/search", json={"q": "x"}).json() == {"q": "x"}
    client.post("/search", json={"q": "x"})
    client.post("/search", json={"q": "y"})
    assert calls["n"] == 2


class FakeConn:
    def __init__(self):
        self.version = 1
        self.queries = 0

    def execute(self, _sql):
        self.queries += 1
        return self

    def fetchone(self):
        return {"v": self.version}


def test_caches_clear_when_data_version_changes(monkeypatch):
    monkeypatch.setattr(cache_mod, "_version", {"value": None, "checked": float("-inf")})
    c = TTLCache(ttl=1000, maxsize=10)
    monkeypatch.setattr(cache_mod, "_registry", [c])
    conn = FakeConn()

    ensure_fresh(conn, now=0)
    c.set("k", b"old", now=0)
    ensure_fresh(conn, now=30)  # within the check interval: no query
    assert conn.queries == 1 and c.get("k", now=30) == b"old"

    conn.version = 2  # nightly update ran
    ensure_fresh(conn, now=61)
    assert conn.queries == 2 and c.get("k", now=61) is None
