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
    "dividend_yield": {"label": "Dividend Yield", "unit": "%", "higher_is_better": True},
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
}

ALIASES = {
    "mcap": "market_cap", "marketcap": "market_cap", "price": "close", "ltp": "close",
    "de": "debt_to_equity", "d/e": "debt_to_equity", "debt": "debt_to_equity",
    "dy": "dividend_yield", "yield": "dividend_yield",
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
        f"SELECT s.symbol, s.name, s.sector, m.as_of, {columns} "
        "FROM stock_metrics m JOIN stocks s USING (symbol) "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY m.{sort_col} {direction} NULLS LAST "
        "LIMIT %s"
    )
    return sql, params
