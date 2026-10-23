from datetime import date

import pytest

from app.ingest.results import pick_filings
from app.ingest.xbrl import parse_results

XBRL = """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:in-capmkt="http://www.sebi.gov.in/xbrl/in-capmkt">
  <xbrli:context id="OneD"><xbrli:period><xbrli:startDate>2026-01-01</xbrli:startDate><xbrli:endDate>2026-03-31</xbrli:endDate></xbrli:period></xbrli:context>
  <in-capmkt:RevenueFromOperations contextRef="OneD" decimals="-7" unitRef="INR">172920000000</in-capmkt:RevenueFromOperations>
  <in-capmkt:RevenueFromOperations contextRef="FourD" decimals="-7" unitRef="INR">543640000000</in-capmkt:RevenueFromOperations>
  <in-capmkt:ProfitBeforeTax contextRef="FourD" unitRef="INR">6150000000</in-capmkt:ProfitBeforeTax>
  <in-capmkt:ProfitBeforeExceptionalItemsAndTax contextRef="FourD" unitRef="INR">6150000000</in-capmkt:ProfitBeforeExceptionalItemsAndTax>
  <in-capmkt:FinanceCosts contextRef="FourD" unitRef="INR">3920000000</in-capmkt:FinanceCosts>
  <in-capmkt:DepreciationDepletionAndAmortisationExpense contextRef="FourD" unitRef="INR">15970000000</in-capmkt:DepreciationDepletionAndAmortisationExpense>
  <in-capmkt:OtherIncome contextRef="FourD" unitRef="INR">13960000000</in-capmkt:OtherIncome>
  <in-capmkt:ProfitOrLossAttributableToOwnersOfParent contextRef="OneD" unitRef="INR">1740000000</in-capmkt:ProfitOrLossAttributableToOwnersOfParent>
  <in-capmkt:ProfitOrLossAttributableToOwnersOfParent contextRef="FourD" unitRef="INR">3660000000</in-capmkt:ProfitOrLossAttributableToOwnersOfParent>
  <in-capmkt:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations contextRef="FourD" unitRef="INRPerShare">0.4</in-capmkt:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations>
  <in-capmkt:PaidUpValueOfEquityShareCapital contextRef="FourD" unitRef="INR">9190000000</in-capmkt:PaidUpValueOfEquityShareCapital>
  <in-capmkt:FaceValueOfEquityShareCapital contextRef="FourD" unitRef="INRPerShare">1</in-capmkt:FaceValueOfEquityShareCapital>
  <in-capmkt:CashFlowsFromUsedInOperatingActivities contextRef="FourD" unitRef="INR">6320000000</in-capmkt:CashFlowsFromUsedInOperatingActivities>
  <in-capmkt:Assets contextRef="OneI" unitRef="INR">407360000000</in-capmkt:Assets>
  <in-capmkt:EquityAttributableToOwnersOfParent contextRef="OneI" unitRef="INR">309800000000</in-capmkt:EquityAttributableToOwnersOfParent>
  <in-capmkt:BorrowingsCurrent contextRef="OneI" unitRef="INR">0</in-capmkt:BorrowingsCurrent>
  <in-capmkt:Assets contextRef="PY_I" unitRef="INR">1</in-capmkt:Assets>
  <in-capmkt:NameOfTheCompany contextRef="OneD">Example Ltd</in-capmkt:NameOfTheCompany>
</xbrli:xbrl>"""


def test_march_filing_yields_quarter_and_full_year():
    rows = parse_results(XBRL, "ETERNAL", date(2026, 3, 31), "consolidated xbrl")
    q, fy = rows
    assert q["period_type"] == "Q" and q["revenue"] == pytest.approx(17292) and q["net_profit"] == pytest.approx(174)
    assert fy["period_type"] == "FY"
    assert fy["revenue"] == pytest.approx(54364)
    assert fy["net_profit"] == pytest.approx(366)
    assert fy["operating_profit"] == pytest.approx(615 + 392 + 1597 - 1396)
    assert fy["shares_outstanding"] == 9_190_000_000
    assert fy["total_assets"] == pytest.approx(40736)  # OneI, not prior year
    assert fy["total_equity"] == pytest.approx(30980)
    assert fy["total_debt"] == 0
    assert fy["eps"] == 0.4


def test_non_march_filing_has_no_fy_row():
    rows = parse_results(XBRL, "ETERNAL", date(2025, 12, 31), "x")
    assert [r["period_type"] for r in rows] == ["Q"]


def test_pick_filings_prefers_consolidated_and_march_years():
    f = lambda d, c: {"period_end": d, "consolidated": c, "xbrl": f"{d}-{c}"}  # noqa: E731
    filings = [
        f(date(2026, 9, 30), False), f(date(2026, 9, 30), True), f(date(2026, 6, 30), True),
        f(date(2026, 3, 31), True), f(date(2025, 12, 31), True), f(date(2025, 3, 31), False),
        f(date(2024, 3, 31), True), f(date(2023, 3, 31), True),
    ]
    picked = pick_filings(filings, years=3, quarters=2)
    assert [p["xbrl"] for p in picked] == [
        "2026-09-30-True", "2026-06-30-True", "2026-03-31-True", "2025-03-31-False", "2024-03-31-True",
    ]
