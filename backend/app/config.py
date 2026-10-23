from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://genscr:genscr@localhost:5432/genscr"
    cors_origins: str = "http://localhost:3000"

    # NSE public archives. Fetch at most once per file per day and cache in Postgres.
    nse_archive_base: str = "https://nsearchives.nseindia.com"
    http_user_agent: str = "Mozilla/5.0 (compatible; genScr/0.1)"
    # Floor of 1s between requests to NSE: we must never hammer the exchange's servers.
    request_delay_seconds: float = Field(1.5, ge=1.0)

    # Public API: per-IP requests per minute. Limits bulk scraping/redistribution of exchange data.
    rate_limit_per_minute: int = Field(90, ge=10)


settings = Settings()
