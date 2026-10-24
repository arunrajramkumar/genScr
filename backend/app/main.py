from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.db import pool
from app.middleware import RateLimiter, make_guard_middleware
from app.routers import calendar, compare, delivery, indices, market, screener, search, shareholding, stocks, valuation, watchlist


@asynccontextmanager
async def lifespan(_: FastAPI):
    pool.open()
    yield
    pool.close()


app = FastAPI(title="genScr API", version="0.1.0", lifespan=lifespan)

limiter = RateLimiter(settings.rate_limit_per_minute)
app.middleware("http")(make_guard_middleware(limiter))

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    max_age=86400,  # browsers cache the preflight for a day
)

# watchlist first: its /stocks/batch must not be captured by stocks' /stocks/{symbol}.
# delivery and shareholding before stocks, so /stocks/{symbol}/delivery and /shareholding are registered ahead of the stocks routes.
for module in (watchlist, delivery, shareholding, valuation, search, stocks, screener, compare, market, indices, calendar):
    app.include_router(module.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
def robots():
    return "User-agent: *\nDisallow: /\n"
