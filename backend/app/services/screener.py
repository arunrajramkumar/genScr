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
    "rsi": "rsi_14", "piotroski": "piotroski_f", "fscore": "piotroski_f", "z": "altman_z",
    "sales_growth": "revenue_growth_yoy", "profit_growth": "profit_growth_yoy",
}

OPS = {">", ">=", "<", "<=", "=", "!="}

PRESETS = [
    {"id": "quality", "name": "Quality Compounders", "description": "High returns on capital, low debt",
     "query": "roe > 18 and roce > 18 and debt_to_equity < 0.5 and market_cap > 1000"},
    {"id": "value", "name": "Value with Strength", "description": "Cheap on earnings and book, financially improving",
     "query": "pe < 15 and pb < 2 and roe > 12 and piotroski_f >= 6"},
    {"id": "growth", "name": "Fast Growers", "description": "20%+ revenue and profit growth",
     "query": "revenue_growth_yoy > 20 and profit_growth_yoy > 20 and roe > 15"},
    {"id": "momentum", "name": "Momentum Leaders", "description": "Near 52-week highs, not overbought",
     "query": "pct_from_52w_high > -5 and return_1y > 30 and rsi_14 < 75"},
    {"id": "safe", "name": "Fortress Balance Sheets", "description": "Low bankruptcy risk, strong F-score",
     "query": "altman_z > 2.6 and debt_to_equity < 0.3 and piotroski_f >= 7"},
    {"id": "oversold", "name": "Oversold Large Caps", "description": "RSI below 30, market cap above ₹5,000 Cr",
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
