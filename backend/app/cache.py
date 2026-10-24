"""Response caching for a small instance: data changes once a day, so cache serialized JSON bytes.

Caching bytes (not Python objects) keeps memory low: a full price history is ~130 KB as JSON
but several MB as Python dicts.
"""

import threading
import time
from collections import OrderedDict
from decimal import Decimal
from functools import wraps

import orjson
from fastapi import Response


class TTLCache:
    """LRU cache whose entries expire after `ttl` seconds."""

    def __init__(self, ttl: float, maxsize: int):
        self.ttl = ttl
        self.maxsize = maxsize
        self._data: OrderedDict = OrderedDict()
        self._lock = threading.Lock()  # sync routes run in a thread pool

    def get(self, key, now: float | None = None):
        now = time.monotonic() if now is None else now
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires, value = item
            if now >= expires:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key, value, now: float | None = None):
        now = time.monotonic() if now is None else now
        with self._lock:
            self._data[key] = (now + self.ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)

    def clear(self):
        with self._lock:
            self._data.clear()

    def __len__(self):
        return len(self._data)


def _default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Not JSON serializable: {type(obj).__name__}")


def dumps(data) -> bytes:
    return orjson.dumps(data, default=_default)


def json_response(body: bytes, max_age: int) -> Response:
    return Response(
        body,
        media_type="application/json",
        headers={"Cache-Control": f"public, max-age={max_age}, stale-while-revalidate=3600"},
    )


def _key(kwargs: dict) -> bytes:
    parts = {k: (v.model_dump() if hasattr(v, "model_dump") else v) for k, v in kwargs.items() if k != "conn"}
    return orjson.dumps(parts, option=orjson.OPT_SORT_KEYS, default=_default)


_registry: list[TTLCache] = []

VERSION_CHECK_SECONDS = 60
_version = {"value": None, "checked": float("-inf")}


def ensure_fresh(conn, now: float | None = None) -> None:
    """Clear every cache when the data changes (checked at most once a minute with one tiny query)."""
    now = time.monotonic() if now is None else now
    if now - _version["checked"] < VERSION_CHECK_SECONDS:
        return
    _version["checked"] = now
    row = conn.execute("SELECT max(updated_at) AS v FROM stock_metrics").fetchone()
    value = row["v"] if row else None
    if _version["value"] is not None and value != _version["value"]:
        clear_all()
    _version["value"] = value


def cached(ttl: float = 43200, maxsize: int = 256, max_age: int = 1800):
    """Cache a route's JSON output by its arguments (excluding the DB connection).

    ttl: server-side lifetime (entries are also dropped as soon as the data changes);
    max_age: how long browsers may reuse the response. Errors (e.g. HTTPException) are never cached.
    """

    def decorator(fn):
        cache = TTLCache(ttl, maxsize)
        _registry.append(cache)

        @wraps(fn)
        def wrapper(*args, **kwargs):
            if kwargs.get("conn") is not None:
                ensure_fresh(kwargs["conn"])
            key = _key(kwargs)
            body = cache.get(key)
            if body is None:
                body = dumps(fn(*args, **kwargs))
                cache.set(key, body)
            return json_response(body, max_age)

        wrapper.cache = cache
        return wrapper

    return decorator


def clear_all():
    for c in _registry:
        c.clear()
