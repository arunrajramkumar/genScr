from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://genscr:genscr@localhost:5432/genscr"
    cors_origins: str = "http://localhost:3000"

    # NSE public archives. Fetch at most once per file per day and cache in Postgres.
    nse_archive_base: str = "https://nsearchives.nseindia.com"
    http_user_agent: str = "Mozilla/5.0 (compatible; genScr/0.1)"
    request_delay_seconds: float = 1.5


settings = Settings()
