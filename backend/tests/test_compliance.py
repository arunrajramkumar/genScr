from datetime import date

import pytest

from app.services.compliance import filter_compliant, is_compliant, violations
from app.services.facts import build_facts
from app.services.screener import FIELDS, PRESETS


@pytest.mark.parametrize("text", [
    "Strong buy on TCS",
    "BUY NOW before it's too late",
    "Target price ₹4,500",
    "price target of 1200",
    "This is a multibagger",
    "multi-bagger stock",
    "Guaranteed returns of 20%",
    "assured returns every month",
    "sure shot trade",
    "risk-free returns",
    "Stock tips for Monday",
    "Tip of the day: RELIANCE",
    "This stock will double in a year",
    "Expected returns: 18% per year",
    "We recommend accumulating",
    "You should buy this",
    "sell call on INFY",
    "upside target of 25%",
])
def test_flags_advice_and_promotional_language(text):
    assert violations(text), text
    assert not is_compliant(text)


@pytest.mark.parametrize("text", [
    "Nothing here is a recommendation to buy, sell or hold any security.",
    "These are not predictions, targets or recommendations.",
    "We do not provide stock tips.",
    "No guaranteed returns: investing involves risk.",
    "Past performance does not indicate future returns.",
    "Earned ₹221 Cr of profit every single day in FY26.",
    "Ended higher in 7 of 9 calendar years (2017 to 2025).",
    "RSI above 70",
    "Highest close since 2016 on 2 Jan 2026.",
])
def test_allows_factual_and_negated_text(text):
    assert is_compliant(text), violations(text)


def test_negation_must_be_in_same_sentence():
    assert not is_compliant("This is not advice. Strong buy at these levels!")


def test_filter_compliant_drops_offending_items():
    items = [
        {"title": "Profit machine", "text": "Earned ₹10 Cr a day."},
        {"title": "Hot pick", "text": "Strong buy, target price ₹900"},
    ]
    assert [i["title"] for i in filter_compliant(items)] == ["Profit machine"]


def test_screener_presets_and_labels_are_factual():
    for p in PRESETS:
        for field in ("name", "description"):
            assert is_compliant(p[field]), (p["id"], violations(p[field]))
    for meta in FIELDS.values():
        assert is_compliant(meta["label"])


def test_generated_facts_are_compliant():
    stock = {"symbol": "X", "sector": "IT", "market_cap": 10000.0, "listing_date": date(2004, 8, 25)}
    fy = [
        {"period_end": date(2026, 3, 31), "net_profit": 3650.0, "revenue": 30000.0, "total_debt": 0.0,
         "total_assets": 50000.0, "cash": 2000.0, "source": "consolidated xbrl"},
        {"period_end": date(2024, 3, 31), "net_profit": 2000.0, "revenue": 15000.0},
    ]
    facts = build_facts(stock, [], fy, {"rank": 3, "total": 400, "sector_rank": 1, "sector_total": 40})
    assert facts
    for f in facts:
        assert is_compliant(f["title"]) and is_compliant(f["text"]), f
        assert f["source"], "every fact must cite its source"


def test_build_facts_filters_non_compliant_output(monkeypatch):
    import app.services.facts as facts_mod

    original = facts_mod.inr
    monkeypatch.setattr(facts_mod, "inr", lambda n, d=0: original(n, d) + " (strong buy)")
    stock = {"symbol": "X", "market_cap": 1000.0}
    fy = [{"period_end": date(2026, 3, 31), "net_profit": 365.0}]
    assert facts_mod.build_facts(stock, [], fy, None) == []
