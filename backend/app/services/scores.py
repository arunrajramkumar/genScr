"""Fundamental quality / risk scores and valuation ratios.

Inputs are dicts shaped like rows of the `fundamentals` table (₹ crore),
for the latest financial year (`cur`) and the one before it (`prev`).
"""


def _div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def piotroski_f(cur: dict, prev: dict | None) -> int | None:
    """Piotroski F-score (0-9). Operating margin stands in for gross margin,
    which Indian filings don't report consistently."""
    if not prev:
        return None
    roa, roa_prev = _div(cur.get("net_profit"), cur.get("total_assets")), _div(prev.get("net_profit"), prev.get("total_assets"))
    cfo = cur.get("cfo")
    if roa is None or cfo is None:
        return None

    lev, lev_prev = _div(cur.get("total_debt"), cur.get("total_assets")), _div(prev.get("total_debt"), prev.get("total_assets"))
    cr = _div(cur.get("current_assets"), cur.get("current_liabilities"))
    cr_prev = _div(prev.get("current_assets"), prev.get("current_liabilities"))
    om, om_prev = _div(cur.get("operating_profit"), cur.get("revenue")), _div(prev.get("operating_profit"), prev.get("revenue"))
    at, at_prev = _div(cur.get("revenue"), cur.get("total_assets")), _div(prev.get("revenue"), prev.get("total_assets"))
    sh, sh_prev = cur.get("shares_outstanding"), prev.get("shares_outstanding")

    def gt(a, b):
        return a is not None and b is not None and a > b

    checks = [
        roa > 0,
        cfo > 0,
        gt(roa, roa_prev),
        gt(cfo, cur.get("net_profit")),
        gt(lev_prev, lev) or (lev == 0 and lev_prev == 0),
        gt(cr, cr_prev),
        sh is not None and sh_prev is not None and sh <= sh_prev,
        gt(om, om_prev),
        gt(at, at_prev),
    ]
    return sum(bool(c) for c in checks)


def altman_z(cur: dict) -> float | None:
    """Altman Z'' (emerging-markets / non-manufacturer variant, without the 3.25 constant).
    > 2.6 safe, 1.1-2.6 grey zone, < 1.1 distress."""
    ta = cur.get("total_assets")
    equity = cur.get("total_equity")
    if not ta or equity is None:
        return None
    ca, cl = cur.get("current_assets"), cur.get("current_liabilities")
    pbt, interest = cur.get("pbt"), cur.get("interest") or 0
    reserves = cur.get("reserves")
    liabilities = ta - equity
    if None in (ca, cl, pbt, reserves) or liabilities <= 0:
        return None
    x1 = (ca - cl) / ta
    x2 = reserves / ta
    x3 = (pbt + interest) / ta
    x4 = equity / liabilities
    return 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4


def sane_shares(reported: float | None, implied: float | None) -> float | None:
    """Share count, cross-checked against net profit / EPS.

    Some filings carry a mis-scaled paid-up capital or face value (FIVESTAR once reported 100,000x its real
    share count). Profit / EPS uses weighted-average shares, so it is only trusted for gross (>3x) mismatches.
    """
    if reported and implied and not (1 / 3 <= reported / implied <= 3):
        return implied
    return reported or implied


def fundamental_ratios(cur: dict | None, prev: dict | None, close: float | None) -> dict:
    """Valuation and return ratios. Percentages are returned as e.g. 18.5 for 18.5%."""
    out = dict.fromkeys(
        ["market_cap", "pe", "pb", "roe", "roce", "debt_to_equity", "net_margin",
         "revenue_growth_yoy", "profit_growth_yoy", "piotroski_f", "altman_z", "dividend_yield"]
    )
    if not cur:
        return out

    np_ = cur.get("net_profit")
    shares = sane_shares(cur.get("shares_outstanding"), np_ * 1e7 / cur["eps"] if np_ and cur.get("eps") and np_ > 0 and cur["eps"] > 0 else None)
    equity = cur.get("total_equity")
    debt = cur.get("total_debt") or 0

    if close and shares:
        out["market_cap"] = close * shares / 1e7  # ₹ → ₹ crore
    mcap = out["market_cap"]
    if mcap and np_ and np_ > 0:
        out["pe"] = mcap / np_
    if mcap and equity and equity > 0:
        out["pb"] = mcap / equity
    dividends = cur.get("dividends_paid")
    if mcap and dividends and dividends > 0:
        out["dividend_yield"] = dividends / mcap * 100  # trailing: last FY's dividends paid / today's market cap

    avg_equity = equity
    if prev and prev.get("total_equity") and equity:
        avg_equity = (equity + prev["total_equity"]) / 2
    if avg_equity and avg_equity > 0 and np_ is not None:
        out["roe"] = np_ / avg_equity * 100

    pbt = cur.get("pbt")
    if pbt is not None and equity:
        capital_employed = equity + debt
        if capital_employed > 0:
            out["roce"] = (pbt + (cur.get("interest") or 0)) / capital_employed * 100

    if equity and equity > 0:
        out["debt_to_equity"] = debt / equity
    if np_ is not None and cur.get("revenue"):
        out["net_margin"] = np_ / cur["revenue"] * 100

    if prev:
        def growth(key):
            a, b = cur.get(key), prev.get(key)
            if a is None or not b or b < 0:
                return None
            return (a / b - 1) * 100

        out["revenue_growth_yoy"] = growth("revenue")
        out["profit_growth_yoy"] = growth("net_profit")

    out["piotroski_f"] = piotroski_f(cur, prev)
    out["altman_z"] = altman_z(cur)
    return out
