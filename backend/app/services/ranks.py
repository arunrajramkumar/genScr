"""Percentile standing of a stock among its sector peers and the whole market (pure, no I/O).

Percentile = share of other companies (with a value) whose figure is lower than this stock's; rank 1 = highest
value. The same direction for every metric, so a high position is never presented as better. Descriptive, not a rating.
"""

RANKED = {
    "roe": "ROE",
    "roce": "ROCE",
    "net_margin": "Net margin",
    "revenue_growth_yoy": "Revenue growth",
    "profit_growth_yoy": "Profit growth",
    "pe": "P/E",
    "pb": "P/B",
    "debt_to_equity": "Debt / equity",
    "dividend_yield": "Dividend yield",
    "return_1y": "1-year return",
    "piotroski_f": "Piotroski F-score",
    "market_cap": "Market cap",
}


def _percentile(value: float, values: list[float]) -> tuple[float, int]:
    lower = sum(1 for v in values if v < value)
    rank = sum(1 for v in values if v > value) + 1
    return round(lower / max(len(values) - 1, 1) * 100, 1) if len(values) > 1 else 100.0, rank


def percentile_ranks(symbol: str, rows: list[dict]) -> dict:
    """rows: [{symbol, sector, <metric fields>}] for all stocks with metrics."""
    target = next((r for r in rows if r["symbol"] == symbol), None)
    if target is None:
        return {"sector": None, "sector_size": 0, "metrics": []}
    sector = target.get("sector")
    peers = [r for r in rows if sector and r.get("sector") == sector]
    out = []
    for field, label in RANKED.items():
        v = target.get(field)
        if v is None or (field == "pe" and v <= 0):
            continue
        all_vals = [r[field] for r in rows if r.get(field) is not None and not (field == "pe" and r[field] <= 0)]
        sec_vals = [r[field] for r in peers if r.get(field) is not None and not (field == "pe" and r[field] <= 0)]
        mp, mr = _percentile(v, all_vals)
        item = {"field": field, "label": label, "value": v,
                "market_percentile": mp, "market_rank": mr, "market_total": len(all_vals)}
        if len(sec_vals) >= 5:
            sp, sr = _percentile(v, sec_vals)
            item.update({"sector_percentile": sp, "sector_rank": sr, "sector_total": len(sec_vals)})
        out.append(item)
    return {"sector": sector, "sector_size": len(peers), "metrics": out}
