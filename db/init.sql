-- genScr schema. Runs automatically on first `docker compose up` (empty volume).
-- Money values in fundamentals / metrics are in ₹ crore unless noted.

-- TimescaleDB is optional: plain Postgres (Neon, Supabase, Homebrew) works, just without hypertables.
DO $$ BEGIN
    CREATE EXTENSION IF NOT EXISTS timescaledb;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'TimescaleDB not available; prices will be a plain table';
END $$;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Master list of listed equities (from NSE EQUITY_L.csv + index constituent files for sector).
CREATE TABLE IF NOT EXISTS stocks (
    symbol        TEXT PRIMARY KEY,
    isin          TEXT,
    name          TEXT NOT NULL,
    series        TEXT,
    listing_date  DATE,
    face_value    NUMERIC(12, 2),
    sector        TEXT,
    industry      TEXT,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS stocks_name_trgm ON stocks USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS stocks_sector_idx ON stocks (sector);

-- Daily end-of-day prices from the NSE bhavcopy.
CREATE TABLE IF NOT EXISTS prices (
    symbol      TEXT NOT NULL,
    trade_date  DATE NOT NULL,
    series      TEXT,
    open        NUMERIC(14, 2),
    high        NUMERIC(14, 2),
    low         NUMERIC(14, 2),
    close       NUMERIC(14, 2),
    prev_close  NUMERIC(14, 2),
    volume      BIGINT,
    turnover    NUMERIC(20, 2),  -- in ₹ (not crore)
    trades      BIGINT,
    PRIMARY KEY (symbol, trade_date)
);
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable('prices', 'trade_date', if_not_exists => TRUE, migrate_data => TRUE);
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS prices_date_idx ON prices (trade_date DESC);

-- Reported financials (from company filings). Q = quarter, FY = financial year.
CREATE TABLE IF NOT EXISTS fundamentals (
    symbol               TEXT NOT NULL,
    period_end           DATE NOT NULL,
    period_type          TEXT NOT NULL CHECK (period_type IN ('Q', 'FY')),
    revenue              NUMERIC(18, 2),
    operating_profit     NUMERIC(18, 2),
    depreciation         NUMERIC(18, 2),
    interest             NUMERIC(18, 2),
    pbt                  NUMERIC(18, 2),
    net_profit           NUMERIC(18, 2),
    eps                  NUMERIC(14, 2),
    total_assets         NUMERIC(18, 2),
    total_equity         NUMERIC(18, 2),
    reserves             NUMERIC(18, 2),
    total_debt           NUMERIC(18, 2),
    current_assets       NUMERIC(18, 2),
    current_liabilities  NUMERIC(18, 2),
    cash                 NUMERIC(18, 2),
    cfo                  NUMERIC(18, 2),
    capex                NUMERIC(18, 2),
    shares_outstanding   BIGINT,
    source               TEXT,
    PRIMARY KEY (symbol, period_end, period_type)
);

-- Pre-computed snapshot per stock, rebuilt nightly. The screener queries this table only.
CREATE TABLE IF NOT EXISTS stock_metrics (
    symbol              TEXT PRIMARY KEY,
    as_of               DATE NOT NULL,
    close               NUMERIC(14, 2),
    change_pct          NUMERIC(10, 2),
    high_52w            NUMERIC(14, 2),
    low_52w             NUMERIC(14, 2),
    pct_from_52w_high   NUMERIC(10, 2),
    return_1m           NUMERIC(10, 2),
    return_1y           NUMERIC(10, 2),
    avg_volume_20d      BIGINT,
    turnover            NUMERIC(14, 2),  -- latest day, ₹ crore
    rsi_14              NUMERIC(6, 2),
    sma_50              NUMERIC(14, 2),
    sma_200             NUMERIC(14, 2),
    market_cap          NUMERIC(18, 2),
    pe                  NUMERIC(12, 2),
    pb                  NUMERIC(12, 2),
    roe                 NUMERIC(10, 2),
    roce                NUMERIC(10, 2),
    debt_to_equity      NUMERIC(10, 2),
    net_margin          NUMERIC(10, 2),
    revenue_growth_yoy  NUMERIC(10, 2),
    profit_growth_yoy   NUMERIC(10, 2),
    piotroski_f         SMALLINT,
    altman_z            NUMERIC(8, 2),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS stock_metrics_mcap_idx ON stock_metrics (market_cap DESC NULLS LAST);
