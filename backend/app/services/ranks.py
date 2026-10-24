"""Percentile standing of a stock among its sector peers and the whole market (pure, no I/O).

Percentile = share of companies (with a value) that this stock is ahead of, where "ahead"
follows the metric's direction (higher ROE, lower debt/equity). Descriptive, not a rating.
"""

RANKED = {
    "roe": ("ROE", True),
    "roce": ("ROCE", True),
    "net_margin": ("Net margin", True),
    "revenue_growth_yoy": ("Revenue growth", True),
    "profit_growth_yoy": ("Profit growth", True),
    "pe": ("P/E (lower first)", False),
    "pb": ("P/B (lower first)", False),
    "debt_to_equity": ("Debt / equity (lower first)", False),
    "dividend_yield": ("Dividend yield", True),
    "return_1y": ("1-year return", True),
    "piotroski_f": ("Piotroski F-score", True),
    "market_cap": ("Size (market cap)", True),
}


def _percentile(value: float, values: list[float], higher_is_better: bool) -> tuple[float, int]:
    behind = sum(1 for v in values if (v < value if higher_is_better else v > value))
    rank = sum(1 for v in values if (v > value if higher_is_better else v < value)) + 1
    return round(behind / max(len(values) - 1, 1) * 100, 1) if len(values) > 1 else 100.0, rank


def percentile_ranks(symbol: str, rows: list[dict]) -> dict:
    """rows: [{symbol, sector, <metric fields>}] for all stocks with metrics."""
    target = next((r for r in rows if r["symbol"] == symbol), None)
    if target is None:
        return {"sector": None, "sector_size": 0, "metrics": []}
    sector = target.get("sector")
    peers = [r for r in rows if sector and r.get("sector") == sector]
    out = []
    for field, (label, hib) in RANKED.items():
        v = target.get(field)
        if v is None or (field == "pe" and v <= 0):
            continue
        all_vals = [r[field] for r in rows if r.get(field) is not None and not (field == "pe" and r[field] <= 0)]
        sec_vals = [r[field] for r in peers if r.get(field) is not None and not (field == "pe" and r[field] <= 0)]
        mp, mr = _percentile(v, all_vals, hib)
        item = {"field": field, "label": label, "value": v,
                "market_percentile": mp, "market_rank": mr, "market_total": len(all_vals)}
        if len(sec_vals) >= 5:
            sp, sr = _percentile(v, sec_vals, hib)
            item.update({"sector_percentile": sp, "sector_rank": sr, "sector_total": len(sec_vals)})
        out.append(item)
    return {"sector": sector, "sector_size": len(peers), "metrics": out}
