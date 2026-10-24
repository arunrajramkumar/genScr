"""Parse NSE/BSE financial-results XBRL filings into `fundamentals` rows (pure, no I/O).

Handles both the legacy `in-bse-fin` taxonomy and the newer Integrated Filing
`in-capmkt` taxonomy; facts are matched by local name, so the prefix doesn't matter.

Context IDs are used rather than context dates (older filings sometimes carry wrong dates):
    OneD  = current quarter            FourD = year-to-date (full year in a March filing)
    OneI  = balance sheet at period end
"""

import xml.etree.ElementTree as ET
from datetime import date

CRORE = 1e7


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def extract_facts(xml_text: str) -> dict[str, dict[str, float]]:
    """{concept: {contextRef: value}} for numeric facts."""
    facts: dict[str, dict[str, float]] = {}
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    for el in root:
        ctx = el.get("contextRef")
        if not ctx or el.text is None:
            continue
        try:
            value = float(el.text.strip())
        except ValueError:
            continue
        facts.setdefault(_local(el.tag), {})[ctx] = value
    return facts


def _first(facts: dict, ctx: str, *names: str) -> float | None:
    for n in names:
        v = facts.get(n, {}).get(ctx)
        if v is not None:
            return v
    return None


def _cr(v: float | None) -> float | None:
    return round(v / CRORE, 2) if v is not None else None


def _income_statement(facts: dict, ctx: str, face_value: float | None = None) -> dict:
    revenue = _first(facts, ctx, "RevenueFromOperations", "Income")
    other_income = _first(facts, ctx, "OtherIncome")
    interest = _first(facts, ctx, "FinanceCosts")
    depreciation = _first(facts, ctx, "DepreciationDepletionAndAmortisationExpense")
    pbt = _first(facts, ctx, "ProfitBeforeTax", "ProfitLossFromOrdinaryActivitiesBeforeTax", "ProfitLossBeforeTax")
    pre_exceptional = _first(facts, ctx, "ProfitBeforeExceptionalItemsAndTax") or pbt

    operating_profit = None  # EBITDA excluding other income; banks report pre-provision profit
    if pre_exceptional is not None and None not in (interest, depreciation):
        operating_profit = pre_exceptional + interest + depreciation - (other_income or 0)
    else:
        operating_profit = _first(facts, ctx, "OperatingProfitBeforeProvisionAndContingencies")

    dividends = _first(facts, ctx, "DividendsPaidClassifiedAsFinancingActivities")  # cash outflow; sign varies
    # Paid-up capital sits on the period (most filers) or the balance-sheet date (insurers).
    paid_up = (_first(facts, ctx, "PaidUpValueOfEquityShareCapital", "PaidUpEquityShareCapital")
               or _first(facts, "OneI", "PaidUpValueOfEquityShareCapital", "PaidUpEquityShareCapital", "ShareCapital"))
    face = _first(facts, ctx, "FaceValueOfEquityShareCapital") or face_value
    net_profit = _first(
        facts, ctx,
        "ProfitOrLossAttributableToOwnersOfParent", "ProfitLossForPeriod",
        "ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates", "ProfitLossForThePeriod",  # banks
        "ProfitLossAfterTaxAndExtraordinaryItems", "ProfitLossAfterTaxBeforeExtraordinaryItems",  # insurers
    )
    eps = _first(
        facts, ctx,
        "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
        "BasicEarningsLossPerShareFromContinuingOperations",
        "BasicEarningsPerShareAfterExtraordinaryItems", "BasicEarningsPerShareBeforeExtraordinaryItems",
    )
    shares = int(paid_up / face) if paid_up and face else None
    if shares is None and net_profit and eps and eps > 0 and net_profit > 0:
        shares = int(round(net_profit / eps))  # rupees / (rupees per share)
    return {
        "revenue": _cr(revenue),
        "operating_profit": _cr(operating_profit),
        "depreciation": _cr(depreciation),
        "interest": _cr(interest),
        "pbt": _cr(pbt),
        "net_profit": _cr(net_profit),
        "eps": eps,
        "cfo": _cr(_first(facts, ctx, "CashFlowsFromUsedInOperatingActivities")),
        "capex": _cr(_first(
            facts, ctx,
            "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
            "PurchaseOfTangibleAssetsClassifiedAsInvestingActivities",
        )),
        "dividends_paid": _cr(abs(dividends) if dividends is not None else None),
        "shares_outstanding": shares,
    }


def _balance_sheet(facts: dict, ctx: str) -> dict:
    borrowings = [_first(facts, ctx, "BorrowingsCurrent"), _first(facts, ctx, "BorrowingsNoncurrent")]
    debt = None if all(b is None for b in borrowings) else sum(b or 0 for b in borrowings)
    if debt is None:
        debt = _first(facts, ctx, "Borrowings")  # banks: excludes customer deposits

    equity = _first(facts, ctx, "EquityAttributableToOwnersOfParent", "Equity", "ShareholdersFunds")
    reserves = _first(facts, ctx, "OtherEquity", "ReservesAndSurplus")
    capital = _first(facts, ctx, "Capital")
    if equity is None and capital is not None and reserves is not None:  # banks
        equity = capital + reserves
    return {
        "total_assets": _cr(_first(facts, ctx, "Assets")),
        "total_equity": _cr(equity),
        "reserves": _cr(reserves),
        "total_debt": _cr(debt),
        "current_assets": _cr(_first(facts, ctx, "CurrentAssets")),
        "current_liabilities": _cr(_first(facts, ctx, "CurrentLiabilities")),
        "cash": _cr(_first(facts, ctx, "CashAndCashEquivalents", "CashAndBalancesWithReserveBankOfIndia")),
    }


def parse_results(xml_text: str, symbol: str, period_end: date, source: str, face_value: float | None = None) -> list[dict]:
    """Rows for one filing: always the quarter (Q); plus the full year (FY) for March filings.
    face_value (from NSE's equity list) is a fallback when the filing omits it (e.g. insurers)."""
    facts = extract_facts(xml_text)
    balance = _balance_sheet(facts, "OneI")
    rows = []

    quarter = _income_statement(facts, "OneD", face_value)
    if quarter["revenue"] is not None or quarter["net_profit"] is not None:
        # Quarterly cash flow is rarely reported; keep Q rows to P&L + balance sheet.
        rows.append({**quarter, **balance, "cfo": None, "capex": None, "dividends_paid": None,
                     "symbol": symbol, "period_end": period_end, "period_type": "Q", "source": source})

    if period_end.month == 3:
        year = _income_statement(facts, "FourD", face_value)
        if year["revenue"] is not None or year["net_profit"] is not None:
            rows.append({**year, **balance, "symbol": symbol, "period_end": period_end,
                         "period_type": "FY", "source": source})
    return rows
