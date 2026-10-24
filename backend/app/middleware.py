"""HTTP guardrails: per-IP rate limiting (prevents bulk redistribution of exchange data) and headers."""

import time
from collections import defaultdict, deque

from starlette.requests import Request
from starlette.responses import JSONResponse

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Robots-Tag": "noindex, nofollow",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",  # JSON only: nothing may load or frame it
    "Cross-Origin-Resource-Policy": "cross-origin",  # the API is data plumbing, not content for search engines
}


class RateLimiter:
    """Sliding-window limiter: at most `limit` requests per `window` seconds per key."""

    def __init__(self, limit: int, window: float = 60.0):
        self.limit = limit
        self.window = window
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        q = self.hits[key]
        while q and now - q[0] >= self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        if len(self.hits) > 50_000:  # keep memory bounded
            for k in [k for k, v in self.hits.items() if not v]:
                del self.hits[k]
        return True


def client_ip(request: Request) -> str:
    # Render sits behind Cloudflare, which overwrites CF-Connecting-IP with the real client address. The left-most
    # X-Forwarded-For entry is whatever the client sent, so it is only a fallback (e.g. local proxies).
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def make_guard_middleware(limiter: RateLimiter):
    async def guard(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and path != "/api/health" and not limiter.allow(client_ip(request)):
            response = JSONResponse(
                {"detail": "Too many requests. Please slow down."},
                status_code=429,
                headers={"Retry-After": str(int(limiter.window))},
            )
        else:
            response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response

    return guard
