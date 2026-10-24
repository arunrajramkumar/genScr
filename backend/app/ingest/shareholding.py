"""Load shareholding-pattern history from NSE: promoter / public % per quarter, plus FII / DII / MF %
from each quarter's shareholding XBRL filing.

    python -m app.ingest.shareholding                   # every symbol that has fundamentals
    python -m app.ingest.shareholding --symbols TCS,ITC
    python -m app.ingest.shareholding --quarters 2      # latest two quarters only (scheduled runs)

One master-list request per symbol, plus one XBRL download (about 1 MB) per quarter. Requests are spaced
by REQUEST_DELAY_SECONDS. Filings are quarterly, so scheduled runs only need the latest quarters; the full
history is backfilled once locally and copied to the hosted database with scripts/export_data.sh.
"""

import argparse
import xml.etree.ElementTree as ET
from datetime import date, datetime

import httpx

from app.db import connect
from app.ingest.results import MAX_CONSECUTIVE_FAILURES, NseClient

MASTER = "https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol={symbol}"
QUARTERS = 12

# XBRL category member (lower-case; older filings spell it "MutualFundsOrUtiMember") -> key.
# Institutions (FII/DII) and mutual funds are sub-totals of public holding.
MEMBERS = {
    "shareholdingofpromoterandpromotergroupmember": "promoter",  # only used to detect the unit
    "publicshareholdingmember": "public",                        # only used to detect the unit
    "institutionsforeignmember": "fii_pct",
    "institutionsdomesticmember": "dii_pct",
    "mutualfundsorutimember": "mf_pct",
}
_CATEGORY_AXIS = "CategoryOfShareholdersAxis"
_PERCENT_FACT = "ShareholdingAsAPercentageOfTotalNumberOfShares"

UPSERT = """
INSERT INTO shareholding (symbol, period_end, promoter_pct, public_pct, fii_pct, dii_pct, mf_pct)
VALUES (%(symbol)s, %(period_end)s, %(promoter_pct)s, %(public_pct)s, %(fii_pct)s, %(dii_pct)s, %(mf_pct)s)
ON CONFLICT (symbol, period_end) DO UPDATE SET
    promoter_pct = EXCLUDED.promoter_pct, public_pct = EXCLUDED.public_pct,
    fii_pct = EXCLUDED.fii_pct, dii_pct = EXCLUDED.dii_pct, mf_pct = EXCLUDED.mf_pct
"""


def _pct(v) -> float | None:
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):  # "-" or missing
        return None


def _broadcast(s) -> datetime:
    try:
        return datetime.strptime(s.strip().title(), "%d-%b-%Y %H:%M:%S")
    except (AttributeError, ValueError):
        return datetime.min


def parse_master(rows: list[dict]) -> list[dict]:
    """[{period_end, promoter_pct, public_pct, xbrl}] from NSE's master list, newest first.

    One row per quarter end. A revised filing is listed alongside the original, so the latest broadcast wins.
    """
    latest: dict[date, tuple[datetime, dict]] = {}
    for r in rows or []:
        try:
            period = datetime.strptime(r["date"].strip().title(), "%d-%b-%Y").date()
        except (KeyError, AttributeError, ValueError):
            continue
        promoter = _pct(r.get("pr_and_prgrp"))
        if promoter is None:
            continue
        broadcast = _broadcast(r.get("broadcastDate"))
        if period not in latest or broadcast >= latest[period][0]:
            latest[period] = (broadcast, {
                "period_end": period,
                "promoter_pct": promoter,
                "public_pct": _pct(r.get("public_val")),
                "xbrl": r.get("xbrl") or None,
            })
    return [latest[p][1] for p in sorted(latest, reverse=True)]


def parse_holdings_xbrl(xml: str | bytes, promoter_pct: float | None = None, public_pct: float | None = None) -> dict[str, float]:
    """{fii_pct, dii_pct, mf_pct} (percent) from one quarter's shareholding XBRL. Keys are missing when not filed.

    Newer filings store fractions (0.0901) and older ones store percents (12.47) under the same unit, so the
    scale is picked by matching the promoter/public categories to the master list's figures.
    """
    root = ET.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
    category: dict[str, str] = {}  # context id -> category member, lower-cased
    for ctx in root.iter():
        if ctx.tag.rsplit("}", 1)[-1] != "context" or not ctx.get("id"):
            continue
        for dim in ctx.iter():
            if dim.tag.rsplit("}", 1)[-1] == "explicitMember" and dim.get("dimension", "").endswith(_CATEGORY_AXIS):
                category[ctx.get("id")] = (dim.text or "").strip().rsplit(":", 1)[-1].lower()

    raw: dict[str, float] = {}
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] != _PERCENT_FACT:
            continue
        key = MEMBERS.get(category.get(el.get("contextRef", "")))
        if key is None or key in raw:
            continue
        try:
            raw[key] = float(el.text)
        except (TypeError, ValueError):
            continue

    scale = _scale(raw, promoter_pct, public_pct)
    return {k: round(raw[k] * scale, 2) for k in ("fii_pct", "dii_pct", "mf_pct") if k in raw}


def _scale(raw: dict[str, float], promoter_pct: float | None, public_pct: float | None) -> float:
    """100 if the raw figures are fractions, 1 if they are already percents."""
    refs = [(raw[k], ref) for k, ref in (("promoter", promoter_pct), ("public", public_pct)) if k in raw and ref is not None]
    if not refs:
        return 100.0  # newer taxonomy default
    as_fraction = sum(abs(x * 100 - ref) for x, ref in refs)
    as_percent = sum(abs(x - ref) for x, ref in refs)
    return 100.0 if as_fraction <= as_percent else 1.0


def _holdings_for(nse: NseClient, q: dict) -> dict[str, float]:
    try:
        return parse_holdings_xbrl(nse.text(q["xbrl"]), q["promoter_pct"], q["public_pct"])
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:  # dead link in NSE's index: keep the master-list numbers only
            return {}
        raise
    except ET.ParseError:
        return {}


def load_symbol(nse: NseClient, conn, symbol: str, quarters: int = QUARTERS) -> int:
    # Quarters already parsed keep their FII/DII/MF split: skips one XBRL download (plus NSE's delay) each.
    parsed = {r["period_end"]: r for r in conn.execute(
        "SELECT period_end, fii_pct, dii_pct, mf_pct FROM shareholding WHERE symbol = %s AND fii_pct IS NOT NULL", (symbol,))}
    rows = []
    for q in parse_master(nse.json(MASTER.format(symbol=symbol)))[:quarters]:
        holdings = parsed.get(q["period_end"]) or (_holdings_for(nse, q) if q["xbrl"] else {})
        rows.append({
            "symbol": symbol,
            "period_end": q["period_end"],
            "promoter_pct": q["promoter_pct"],
            "public_pct": q["public_pct"],
            "fii_pct": holdings.get("fii_pct"),
            "dii_pct": holdings.get("dii_pct"),
            "mf_pct": holdings.get("mf_pct"),
        })
    if rows:
        with conn.cursor() as cur:
            cur.executemany(UPSERT, rows)
        conn.commit()
    return len(rows)


def symbols_with_fundamentals(conn) -> list[str]:
    """Most-traded first, so a stopped run still covers the liquid names."""
    sql = """SELECT f.symbol FROM (SELECT DISTINCT symbol FROM fundamentals) f
             LEFT JOIN stock_metrics m USING (symbol) ORDER BY m.turnover DESC NULLS LAST"""
    return [r["symbol"] for r in conn.execute(sql)]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--symbols", help="Comma-separated symbols (default: every symbol with fundamentals)")
    p.add_argument("--quarters", type=int, default=QUARTERS, help="Latest N quarters per symbol")
    a = p.parse_args()

    with connect() as conn:
        symbols = [s.strip().upper() for s in a.symbols.split(",")] if a.symbols else symbols_with_fundamentals(conn)
        nse = NseClient()
        ok = failed = streak = 0
        try:
            for i, symbol in enumerate(symbols, 1):
                try:
                    n = load_symbol(nse, conn, symbol, a.quarters)
                    ok += 1
                    streak = 0
                    print(f"[{i}/{len(symbols)}] {symbol}: {n} quarters", flush=True)
                except Exception as e:  # keep going; one bad filing shouldn't stop the batch
                    conn.rollback()
                    failed += 1
                    streak += 1
                    print(f"[{i}/{len(symbols)}] {symbol}: FAILED {type(e).__name__}: {e}", flush=True)
                    if streak >= MAX_CONSECUTIVE_FAILURES:
                        raise SystemExit(f"Stopping: {streak} failures in a row (NSE is probably blocking this network).") from e
        finally:
            nse.close()
    print(f"done: {ok} ok, {failed} failed.")


if __name__ == "__main__":
    main()
