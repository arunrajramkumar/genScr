import psycopg
from psycopg.rows import dict_row
from psycopg.types.numeric import FloatLoader
from psycopg_pool import ConnectionPool

from app.config import settings


def configure(conn: psycopg.Connection) -> None:
    # NUMERIC -> float directly: avoids slow Decimal objects and Decimal->float conversion on every response.
    conn.adapters.register_loader("numeric", FloatLoader)


pool = ConnectionPool(
    settings.database_url,
    min_size=1,
    max_size=4,  # small instance + free-tier Postgres connection limits
    kwargs={"row_factory": dict_row},
    configure=configure,
    open=False,
)


def get_conn():
    """FastAPI dependency yielding a pooled connection."""
    with pool.connection() as conn:
        yield conn


def connect() -> psycopg.Connection:
    """Standalone connection for ingest jobs."""
    conn = psycopg.connect(settings.database_url, row_factory=dict_row)
    configure(conn)
    return conn
