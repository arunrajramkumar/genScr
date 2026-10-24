"""Screener query language and safe SQL builder.

Queries look like:  roe > 18 and debt_to_equity < 0.5 and market_cap > 1000
Only whitelisted fields and operators are accepted; values are always bound parameters.
"""

import re

FIELDS: dict[str, dict] = {
    "market_cap": {"label": "Market Cap", "unit": "₹ Cr", "higher_is_better": None},
    "close": {"label": "Price", "unit": "₹", "higher_is_better": None},
    "change_pct": {"label": "Day Change", "unit": "%", "higher_is_better": True},
    "pe": {"label": "P/E", "unit": "x", "higher_is_better": False},
    "pb": {"label": "P/B", "unit": "x", "higher_is_better": False},
    "dividend_yield": {"label": "Dividend Yield (TTM)", "unit": "%", "higher_is_better": True},
    "roe": {"label": "ROE", "unit": "%", "higher_is_better": True},
    "roce": {"label": "ROCE", "unit": "%", "higher_is_better": True},
    "debt_to_equity": {"label": "Debt / Equity", "unit": "x", "higher_is_better": False},
    "net_margin": {"label": "Net Margin", "unit": "%", "higher_is_better": True},
    "revenue_growth_yoy": {"label": "Revenue Growth YoY", "unit": "%", "higher_is_better": True},
    "profit_growth_yoy": {"label": "Profit Growth YoY", "unit": "%", "higher_is_better": True},
    "piotroski_f": {"label": "Piotroski F-Score", "unit": "/9", "higher_is_better": True},
    "altman_z": {"label": "Altman Z''", "unit": "", "higher_is_better": True},
    "rsi_14": {"label": "RSI (14)", "unit": "", "higher_is_better": None},
    "return_1m": {"label": "1M Return", "unit": "%", "higher_is_better": True},
    "return_1y": {"label": "1Y Return", "unit": "%", "higher_is_better": True},
    "pct_from_52w_high": {"label": "% from 52W High", "unit": "%", "higher_is_better": True},
    "avg_volume_20d": {"label": "Avg Volume (20D)", "unit": "", "higher_is_better": None},
    "turnover": {"label": "Turnover", "unit": "₹ Cr", "higher_is_better": None},
    "cagr_3y": {"label": "3Y Price CAGR", "unit": "%", "higher_is_better": True},
    "cagr_5y": {"label": "5Y Price CAGR", "unit": "%", "higher_is_better": True},
    "volatility_1y": {"label": "Volatility (1Y)", "unit": "%", "higher_is_better": False},
    "dividend_streak": {"label": "Dividend Streak", "unit": "yrs", "higher_is_better": True},
    "deliv_pct": {"label": "Delivery %", "unit": "%", "higher_is_better": None},
    "deliv_pct_avg_20d": {"label": "Delivery % (20D avg)", "unit": "%", "higher_is_better": None},
    "promoter_pct": {"label": "Promoter Holding", "unit": "%", "higher_is_better": None},
    "promoter_change_1y": {"label": "Promoter Holding Change (1Y)", "unit": "pts", "higher_is_better": None},
}

GROUPS = {
    "Valuation": ["pe", "pb", "dividend_yield", "market_cap"],
    "Quality": ["roe", "roce", "net_margin", "debt_to_equity", "piotroski_f", "altman_z"],
    "Growth": ["revenue_growth_yoy", "profit_growth_yoy"],
    "Returns": ["return_1m", "return_1y", "cagr_3y", "cagr_5y", "change_pct"],
    "Risk & technicals": ["volatility_1y", "pct_from_52w_high", "rsi_14"],
    "Income": ["dividend_streak"],
    "Trading": ["close", "turnover", "avg_volume_20d", "deliv_pct", "deliv_pct_avg_20d"],
    "Ownership": ["promoter_pct", "promoter_change_1y"],
}

DESCRIPTIONS = {
    "market_cap": "Company value at today's price (₹ crore)",
    "close": "Latest closing price",
    "change_pct": "Change on the latest trading day",
    "pe": "Market cap ÷ latest annual net profit",
    "pb": "Market cap ÷ book value (equity)",
    "roe": "Net profit ÷ average shareholders' equity",
    "roce": "Operating profit (PBT + interest) ÷ capital employed",
    "debt_to_equity": "Borrowings ÷ shareholders' equity",
    "net_margin": "Net profit ÷ revenue",
    "revenue_growth_yoy": "Latest annual revenue vs the year before",
    "profit_growth_yoy": "Latest annual net profit vs the year before",
    "piotroski_f": "9-point financial strength checklist",
    "altman_z": "Bankruptcy-risk model (higher = safer; not for banks)",
    "rsi_14": "14-day momentum oscillator (0-100)",
    "return_1m": "Price change over ~1 month",
    "return_1y": "Price change over ~1 year",
    "pct_from_52w_high": "How far below the 52-week high (0 = at the high)",
    "avg_volume_20d": "Average shares traded per day (20 days)",
    "turnover": "Value traded on the latest day (₹ crore)",
    "dividend_yield": "Dividends ex-dated in the last 12 months ÷ price",
    "cagr_3y": "Annualised price growth over 3 years (split/bonus-adjusted)",
    "cagr_5y": "Annualised price growth over 5 years (split/bonus-adjusted)",
    "volatility_1y": "Annualised day-to-day price swings over 1 year",
    "dividend_streak": "Consecutive financial years with a dividend",
    "deliv_pct": "Share of traded quantity marked for delivery on the latest day",
    "deliv_pct_avg_20d": "Average delivery share over the last 20 trading days",
    "promoter_pct": "Promoter and promoter-group share of total shares, latest filed quarter",
    "promoter_change_1y": "Change in promoter share vs the same quarter a year earlier (percentage points)",
}

ALIASES = {
    "mcap": "market_cap", "marketcap": "market_cap", "price": "close", "ltp": "close",
    "de": "debt_to_equity", "d/e": "debt_to_equity", "debt": "debt_to_equity",
    "dy": "dividend_yield", "yield": "dividend_yield", "vol": "volatility_1y", "volatility": "volatility_1y",
    "streak": "dividend_streak", "cagr3": "cagr_3y", "cagr5": "cagr_5y",
    "rsi": "rsi_14", "piotroski": "piotroski_f", "fscore": "piotroski_f", "z": "altman_z",
    "sales_growth": "revenue_growth_yoy", "profit_growth": "profit_growth_yoy",
}

OPS = {">", ">=", "<", "<=", "=", "!="}

PRESETS = [
    {"id": "quality", "name": "High ROE & ROCE, low debt", "description": "ROE and ROCE above 18%, debt/equity below 0.5",
     "query": "roe > 18 and roce > 18 and debt_to_equity < 0.5 and market_cap > 1000"},
    {"id": "value", "name": "Low P/E & P/B, F-score 6+", "description": "P/E below 15, P/B below 2, ROE above 12%, Piotroski 6+",
     "query": "pe < 15 and pb < 2 and roe > 12 and piotroski_f >= 6"},
    {"id": "growth", "name": "20%+ revenue & profit growth", "description": "Revenue and profit up more than 20% year on year",
     "query": "revenue_growth_yoy > 20 and profit_growth_yoy > 20 and roe > 15"},
    {"id": "momentum", "name": "Near 52W high, 1Y return 30%+", "description": "Within 5% of 52-week high, RSI below 75",
     "query": "pct_from_52w_high > -5 and return_1y > 30 and rsi_14 < 75"},
    {"id": "safe", "name": "Low leverage, Altman Z'' 2.6+",
     "description": "Altman Z'' above 2.6, debt/equity below 0.3, Piotroski 7+",
     "query": "altman_z > 2.6 and debt_to_equity < 0.3 and piotroski_f >= 7"},
    {"id": "dividend", "name": "Dividend yield 3%+", "description": "Trailing yield above 3%, debt/equity below 1",
     "query": "dividend_yield > 3 and debt_to_equity < 1 and market_cap > 1000"},
    {"id": "streak", "name": "Dividend every year 10+ yrs, yield 2%+",
     "description": "Paid a dividend in each of the last 10+ financial years; trailing yield above 2%",
     "query": "dividend_streak >= 10 and dividend_yield > 2"},
    {"id": "steady", "name": "5Y CAGR 15%+, low volatility",
     "description": "Price grew 15%+ a year over 5 years with annual volatility under 30%",
     "query": "cagr_5y > 15 and volatility_1y < 30"},
    {"id": "oversold", "name": "RSI below 30, large caps", "description": "RSI(14) below 30, market cap above ₹5,000 Cr",
     "query": "rsi_14 < 30 and market_cap > 5000"},
]

_CONDITION = re.compile(r"^\s*([a-z_/0-9]+)\s*(>=|<=|!=|=|>|<)\s*(-?\d+(?:\.\d+)?)\s*$", re.IGNORECASE)
_SPLIT = re.compile(r"\s+and\s+|\s*&&\s*|\n", re.IGNORECASE)


def resolve_field(name: str) -> str:
    key = name.strip().lower()
    key = ALIASES.get(key, key)
    if key not in FIELDS:
        raise ValueError(f"Unknown field '{name}'. Available: {', '.join(FIELDS)}")
    return key


def parse_query(text: str) -> list[dict]:
    filters = []
    for part in _SPLIT.split(text.strip()):
        if not part.strip():
            continue
        m = _CONDITION.match(part)
        if not m:
            raise ValueError(f"Could not understand '{part.strip()}'. Use e.g. 'roe > 15'.")
        field, op, value = m.groups()
        filters.append({"field": resolve_field(field), "op": op, "value": float(value)})
    return filters


def build_sql(
    filters: list[dict],
    sector: str | None = None,
    sort: str = "market_cap",
    order: str = "desc",
    limit: int = 100,
) -> tuple[str, list]:
    where, params = ["TRUE"], []
    for f in filters:
        field = resolve_field(f["field"])
        op = f["op"]
        if op not in OPS:
            raise ValueError(f"Unsupported operator '{op}'")
        where.append(f"m.{field} {op} %s")
        params.append(float(f["value"]))
    if sector:
        where.append("s.sector = %s")
        params.append(sector)

    sort_col = resolve_field(sort)
    direction = "ASC" if order.lower() == "asc" else "DESC"
    limit = max(1, min(int(limit), 500))
    params.append(limit)

    columns = ", ".join(f"m.{c}" for c in FIELDS)
    sql = (
        f"SELECT s.symbol, s.name, s.sector, m.as_of, {columns}, count(*) OVER () AS total_matches "
        "FROM stock_metrics m JOIN stocks s USING (symbol) "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY m.{sort_col} {direction} NULLS LAST "
        "LIMIT %s"
    )
    return sql, params


def distribution(values: list[float], bins: int = 24) -> dict:
    """Percentiles and a histogram clipped to the 2nd-98th percentile (so outliers don't flatten it)."""
    v = sorted(float(x) for x in values)
    n = len(v)
    if n == 0:
        return {"count": 0}

    def q(p: float) -> float:
        i = (n - 1) * p
        lo, hi = int(i), min(int(i) + 1, n - 1)
        return v[lo] + (v[hi] - v[lo]) * (i - lo)

    lo, hi = q(0.02), q(0.98)
    width = (hi - lo) / bins if hi > lo else 1.0
    counts = [0] * bins
    for x in v:
        if lo <= x <= hi:
            counts[min(int((x - lo) / width), bins - 1)] += 1
    return {
        "count": n,
        "min": v[0], "max": v[-1],
        "p10": round(q(0.10), 4), "p25": round(q(0.25), 4), "p50": round(q(0.50), 4),
        "p75": round(q(0.75), 4), "p90": round(q(0.90), 4),
        "hist_lo": round(lo, 4), "hist_hi": round(hi, 4), "hist": counts,
    }
