import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings

pool = ConnectionPool(
    settings.database_url,
    min_size=1,
    max_size=10,
    kwargs={"row_factory": dict_row},
    open=False,
)


def get_conn():
    """FastAPI dependency yielding a pooled connection."""
    with pool.connection() as conn:
        yield conn


def connect() -> psycopg.Connection:
    """Standalone connection for ingest jobs."""
    return psycopg.connect(settings.database_url, row_factory=dict_row)
