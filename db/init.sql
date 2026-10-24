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
    dividends_paid       NUMERIC(18, 2),
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
    dividend_yield      NUMERIC(8, 2),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS stock_metrics_mcap_idx ON stock_metrics (market_cap DESC NULLS LAST);

-- Dividends, bonuses, splits, rights, buybacks, demergers (from NSE corporate actions).
CREATE TABLE IF NOT EXISTS corporate_actions (
    symbol       TEXT NOT NULL,
    ex_date      DATE NOT NULL,
    kind         TEXT NOT NULL CHECK (kind IN ('dividend', 'bonus', 'split', 'rights', 'buyback', 'demerger')),
    amount       NUMERIC(14, 4),   -- dividend per share in ₹, as declared
    ratio_new    INT,              -- bonus/rights: new shares ...
    ratio_held   INT,              -- ... for every N held
    old_fv       NUMERIC(10, 2),   -- split: face value before
    new_fv       NUMERIC(10, 2),   -- split: face value after
    price        NUMERIC(14, 2),   -- rights issue price
    record_date  DATE,
    subject      TEXT,             -- original NSE wording
    PRIMARY KEY (symbol, ex_date, kind)
);
CREATE INDEX IF NOT EXISTS corporate_actions_date_idx ON corporate_actions (ex_date);

-- Daily closes and valuation of every NSE index (from NSE's ind_close_all file).
CREATE TABLE IF NOT EXISTS index_prices (
    index_name   TEXT NOT NULL,
    trade_date   DATE NOT NULL,
    open         NUMERIC(14, 2),
    high         NUMERIC(14, 2),
    low          NUMERIC(14, 2),
    close        NUMERIC(14, 2),
    change_pct   NUMERIC(8, 2),
    pe           NUMERIC(8, 2),
    pb           NUMERIC(8, 2),
    div_yield    NUMERIC(6, 2),
    turnover_cr  NUMERIC(16, 2),
    PRIMARY KEY (index_name, trade_date)
);
CREATE INDEX IF NOT EXISTS index_prices_date_idx ON index_prices (trade_date);

-- Index membership (from NSE's index constituent files).
CREATE TABLE IF NOT EXISTS index_constituents (
    index_name  TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (index_name, symbol)
);
CREATE INDEX IF NOT EXISTS index_constituents_symbol_idx ON index_constituents (symbol);

-- Ticker renames (e.g. ZOMATO -> ETERNAL), used to stitch price history together.
CREATE TABLE IF NOT EXISTS symbol_changes (
    old_symbol      TEXT NOT NULL,
    new_symbol      TEXT NOT NULL,
    effective_date  DATE NOT NULL,
    PRIMARY KEY (old_symbol, new_symbol, effective_date)
);

-- Migrations for databases created before these columns existed (safe to re-run).
ALTER TABLE fundamentals  ADD COLUMN IF NOT EXISTS dividends_paid NUMERIC(18, 2);
ALTER TABLE stock_metrics ADD COLUMN IF NOT EXISTS dividend_yield NUMERIC(8, 2);
ALTER TABLE stock_metrics ADD COLUMN IF NOT EXISTS cagr_3y NUMERIC(10, 2);
ALTER TABLE stock_metrics ADD COLUMN IF NOT EXISTS cagr_5y NUMERIC(10, 2);
ALTER TABLE stock_metrics ADD COLUMN IF NOT EXISTS volatility_1y NUMERIC(8, 2);
ALTER TABLE stock_metrics ADD COLUMN IF NOT EXISTS dividend_streak SMALLINT;
