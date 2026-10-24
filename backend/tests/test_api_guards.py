import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import app
from app.middleware import SECURITY_HEADERS, RateLimiter, make_guard_middleware

client = TestClient(app)  # no context manager: lifespan (DB pool) is not started


def test_api_sends_noindex_and_security_headers():
    r = client.get("/api/health")
    assert r.status_code == 200
    for k, v in SECURITY_HEADERS.items():
        assert r.headers[k] == v


def test_api_robots_disallows_crawling():
    r = client.get("/robots.txt")
    assert r.status_code == 200 and "Disallow: /" in r.text


def test_rate_limiter_window():
    rl = RateLimiter(limit=3, window=60)
    assert all(rl.allow("ip", now=t) for t in (0, 1, 2))
    assert not rl.allow("ip", now=3)
    assert rl.allow("other", now=3)  # per-client
    assert rl.allow("ip", now=61)  # window slid


def test_middleware_returns_429_when_limit_exceeded():
    mini = FastAPI()
    mini.middleware("http")(make_guard_middleware(RateLimiter(limit=2)))

    @mini.get("/api/data")
    def data():
        return {"ok": True}

    @mini.get("/api/health")
    def health():
        return {"ok": True}

    c = TestClient(mini)
    assert [c.get("/api/data").status_code for _ in range(3)] == [200, 200, 429]
    r = c.get("/api/data")
    assert r.headers["Retry-After"] == "60" and r.headers["X-Robots-Tag"]
    assert c.get("/api/health").status_code == 200  # health checks are never limited
    # X-Forwarded-For identifies the client behind a proxy
    assert c.get("/api/data", headers={"x-forwarded-for": "1.2.3.4"}).status_code == 200


def test_nse_request_delay_has_a_floor():
    with pytest.raises(ValidationError):
        Settings(request_delay_seconds=0.2)
    assert Settings(request_delay_seconds=1.0).request_delay_seconds == 1.0


def test_rate_limit_cannot_be_disabled():
    with pytest.raises(ValidationError):
        Settings(rate_limit_per_minute=0)


def test_docs_and_schema_are_hidden_by_default():
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_client_ip_prefers_cloudflare_header_over_spoofable_forwarded_for():
    from starlette.requests import Request

    from app.middleware import client_ip

    def req(headers):
        return Request({"type": "http", "headers": [(k.encode(), v.encode()) for k, v in headers.items()], "client": ("10.0.0.1", 1)})

    assert client_ip(req({"cf-connecting-ip": "203.0.113.9", "x-forwarded-for": "1.2.3.4, 203.0.113.9"})) == "203.0.113.9"
    assert client_ip(req({"x-forwarded-for": "1.2.3.4"})) == "1.2.3.4"
    assert client_ip(req({})) == "10.0.0.1"


def test_screener_rejects_oversized_or_invalid_filters():
    from app.routers.screener import ScreenRequest

    with pytest.raises(ValidationError):
        ScreenRequest(filters=[{"field": "pe", "op": "<", "value": 10}] * 21)
    with pytest.raises(ValidationError):
        ScreenRequest(filters=[{"field": "pe", "op": "<", "value": "nan"}])
    with pytest.raises(ValidationError):
        ScreenRequest(filters=[{"field": "x" * 41, "op": "<", "value": 1}])
    assert len(ScreenRequest(filters=[{"field": "pe", "op": "<", "value": 10}] * 20).filters) == 20
