"""Repo-wide compliance checks: fail CI if user-facing code adds advice-like wording or drops legal safeguards."""

import re
from pathlib import Path

import pytest

from app.services.compliance import violations

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web" / "src"
SCANNED = [
    *WEB.rglob("*.tsx"),
    *WEB.rglob("*.ts"),
    *(ROOT / "backend" / "app").rglob("*.py"),
    ROOT / "README.md",
]
EXEMPT = {ROOT / "backend" / "app" / "services" / "compliance.py"}  # holds the banned-phrase list itself


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("path", [p for p in SCANNED if p not in EXEMPT], ids=lambda p: str(p.relative_to(ROOT)))
def test_no_advice_language_in_user_facing_files(path):
    found = violations(path.read_text(encoding="utf-8"))
    assert not found, f"{path.relative_to(ROOT)}: {found}"


def test_disclaimer_covers_required_points():
    site = _read("web/src/lib/site.ts")
    m = re.search(r"export const DISCLAIMER =(.*?);\n", site, re.S)
    assert m, "DISCLAIMER constant missing"
    text = m.group(1).lower()
    for phrase in [
        "educational", "not investment advice", "recommendation to buy, sell or hold",
        "not registered with sebi", "investment adviser or research analyst",
        "not affiliated with nse, bse or sebi", "end-of-day", "past performance does not indicate future results",
        "sebi-registered investment adviser",
    ]:
        assert phrase in text, f"disclaimer must mention: {phrase}"


def test_footer_shows_disclaimer_sources_and_legal_links_on_every_page():
    layout = _read("web/src/app/layout.tsx")
    for needle in ["{DISCLAIMER}", "{DATA_SOURCES}", 'href="/disclaimer"', 'href="/terms"', 'href="/privacy"', "<DisclaimerNotice />"]:
        assert needle in layout, f"layout.tsx must include {needle}"


@pytest.mark.parametrize("page, phrases", [
    ("web/src/app/disclaimer/page.tsx", ["Not investment advice", "No SEBI registration", "No affiliation", "Past performance"]),
    ("web/src/app/terms/page.tsx", ["No scraping", "Information Technology Act", "laws of India", "grievances"]),
    ("web/src/app/privacy/page.tsx", ["Digital Personal Data Protection Act", "Grievance officer", "Your rights", "do not use advertising"]),
])
def test_legal_pages_exist_with_key_sections(page, phrases):
    text = _read(page)
    for p in phrases:
        assert p in text, f"{page} must include '{p}'"


def test_return_projections_are_off_by_default_and_gated():
    site = _read("web/src/lib/site.ts")
    assert 'ENABLE_PROJECTIONS = process.env.NEXT_PUBLIC_ENABLE_PROJECTIONS === "true"' in site
    stock_page = _read("web/src/app/stock/[symbol]/StockView.tsx")
    assert "<Outlook" in stock_page
    for line in stock_page.splitlines():
        if "<Outlook" in line:
            assert "ENABLE_PROJECTIONS &&" in line, "the 5-year outlook must render only when ENABLE_PROJECTIONS is set"
    assert "ENABLE_PROJECTIONS" not in _read("render.yaml"), "do not enable projections in the deploy config"


def test_outlook_and_calculator_carry_their_own_caveats():
    assert "not a forecast" in _read("web/src/components/Outlook.tsx").lower()
    calc = _read("web/src/components/ReturnsCalculator.tsx")
    assert "Past performance does not indicate future returns" in calc
    assert "dividends, taxes and charges not included" in calc


def test_analytics_sections_have_inline_notes():
    assert "not stock picks or recommendations" in _read("web/src/app/screener/page.tsx")
    assert "not a ranking or a recommendation" in _read("web/src/app/compare/page.tsx")
    assert "not investment advice" in _read("web/src/components/DidYouKnow.tsx")
    assert "<StaleDataBanner" in _read("web/src/app/stock/[symbol]/StockView.tsx")


def test_technical_states_are_not_colour_coded_as_buy_or_sell():
    signals = _read("web/src/components/Signals.tsx")
    assert not re.search(r"(overbought|oversold|uptrend|downtrend|bullish|bearish)", signals, re.I)
    for line in signals.splitlines():
        if "out.push" in line and re.search(r"RSI|average|52-week", line):
            assert 'tone: "neutral"' in line, line


def test_status_chips_and_badges_state_facts_not_grades():
    for path in ("web/src/components/Signals.tsx", "web/src/components/ui.tsx"):
        text = _read(path)
        assert not re.search(r'"(Strong|Weak|Average|Safe|Distress)\b', text), path


def test_valuation_percentiles_describe_history_not_value():
    for path in ("web/src/components/ValuationHistory.tsx", "web/src/components/ValuationBar.tsx"):
        text = _read(path)
        assert not re.search(r"(cheap|expensive|undervalued|overvalued|attractive|buy zone|text-(up|down))", text, re.I), path
    history = _read("web/src/components/ValuationHistory.tsx")
    assert "not a valuation call" in history
    assert "weekly readings since" in history


@pytest.mark.parametrize("config", ["web/next.config.mjs", "render.yaml"])
def test_web_security_headers_configured(config):
    cfg = _read(config)
    for header in ["X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy", "Strict-Transport-Security"]:
        assert header in cfg, f"{config} must set {header}"


def test_nginx_sets_security_headers():
    cfg = _read("web/nginx.conf")
    for header in ["X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy"]:
        assert header in cfg
