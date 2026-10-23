"""Load fundamentals from companies' financial-results XBRL filings on NSE.

    python -m app.ingest.results --symbols ETERNAL,TCS
    python -m app.ingest.results --universe nifty500        # ~8 requests per company
    python -m app.ingest.results --universe nifty500 --skip-existing

Filing indexes come from NSE's website (legacy results + SEBI Integrated Filing); the XBRL
documents themselves are mandatory public disclosures on nsearchives. Requests are spaced
by REQUEST_DELAY_SECONDS. Run quarterly after results season, not per user request.
"""

import argparse
import time
from datetime import date, datetime

import httpx

from app.config import settings
from app.db import connect
from app.ingest.fundamentals_csv import COLUMNS, UPSERT
from app.ingest.xbrl import parse_results

SITE = "https://www.nseindia.com"
LEGACY_INDEX = SITE + "/api/corporates-financial-results?index=equities&symbol={symbol}&period={period}"
INTEGRATED_INDEX = SITE + "/api/integrated-filing-results?symbol={symbol}&type=Integrated%20Filing-%20Financials"
MAX_CONSECUTIVE_FAILURES = 15

BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"


class NseClient:
    def __init__(self):
        self.http = httpx.Client(
            headers={"User-Agent": BROWSER_UA, "Accept": "application/json, text/plain, */*", "Referer": SITE + "/"},
            timeout=30,
            follow_redirects=True,
        )
        self.http.get(SITE)  # sets session cookies (status may be 403; cookies still issued)

    def _get(self, url: str) -> httpx.Response:
        time.sleep(settings.request_delay_seconds)
        return self.http.get(url)

    def json(self, url: str):
        resp = self._get(url)
        resp.raise_for_status()
        return resp.json()

    def text(self, url: str) -> str:
        resp = self._get(url)
        resp.raise_for_status()
        return resp.text

    def close(self):
        self.http.close()


def _date(s: str) -> date:
    return datetime.strptime(s.strip().title(), "%d-%b-%Y").date()


def _is_consolidated(label: str | None) -> bool:
    return (label or "").lower() == "consolidated"


def _filing(period_end: str, consolidated: str | None, xbrl: str) -> dict:
    return {"period_end": _date(period_end), "consolidated": _is_consolidated(consolidated), "xbrl": xbrl}


def list_filings(nse: NseClient, symbol: str) -> list[dict]:
    """[{period_end, consolidated, xbrl}] from both indexes, newest first."""
    out = []
    data = nse.json(INTEGRATED_INDEX.format(symbol=symbol))
    for r in (data.get("data") if isinstance(data, dict) else data) or []:
        if r.get("xbrl") and r.get("qe_Date"):
            out.append(_filing(r["qe_Date"], r.get("consolidated"), r["xbrl"]))
    for period in ("Annual", "Quarterly"):
        for r in nse.json(LEGACY_INDEX.format(symbol=symbol, period=period)) or []:
            if r.get("xbrl") and r.get("toDate") and r["xbrl"].endswith(".xml"):
                out.append(_filing(r["toDate"], r.get("consolidated"), r["xbrl"]))
    return sorted(out, key=lambda f: f["period_end"], reverse=True)


def pick_filings(filings: list[dict], years: int, quarters: int) -> list[dict]:
    """One filing per period end (consolidated preferred): the latest `quarters` periods
    plus the March filings for the latest `years` financial years."""
    by_period: dict[date, dict] = {}
    for f in filings:
        cur = by_period.get(f["period_end"])
        if cur is None or (f["consolidated"] and not cur["consolidated"]):
            by_period[f["period_end"]] = f
    periods = sorted(by_period, reverse=True)
    wanted = set(periods[:quarters]) | set([p for p in periods if p.month == 3][:years])
    return [by_period[p] for p in periods if p in wanted]


def load_symbol(nse: NseClient, conn, symbol: str, years: int, quarters: int) -> int:
    rows = []
    for f in pick_filings(list_filings(nse, symbol), years, quarters):
        source = ("consolidated" if f["consolidated"] else "standalone") + " xbrl"
        try:
            xml = nse.text(f["xbrl"])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:  # dead link in NSE's index; skip just this filing
                continue
            raise
        rows += parse_results(xml, symbol, f["period_end"], source)
    if rows:
        with conn.cursor() as cur:
            cur.executemany(UPSERT, [{c: r.get(c) for c in COLUMNS} for r in rows])
        conn.commit()
    return len(rows)


def universe(conn, name: str) -> list[str]:
    if name == "nifty500":
        sql = """SELECT s.symbol FROM stocks s LEFT JOIN stock_metrics m USING (symbol)
                 WHERE s.sector IS NOT NULL ORDER BY m.turnover DESC NULLS LAST"""
    else:
        sql = """SELECT s.symbol FROM stocks s JOIN stock_metrics m USING (symbol)
                 WHERE s.series = 'EQ' ORDER BY m.turnover DESC NULLS LAST"""
    return [r["symbol"] for r in conn.execute(sql)]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--symbols", help="Comma-separated symbols")
    p.add_argument("--universe", choices=["nifty500", "all"])
    p.add_argument("--years", type=int, default=3)
    p.add_argument("--quarters", type=int, default=4)
    p.add_argument("--skip-existing", action="store_true", help="Skip symbols that already have FY data")
    a = p.parse_args()

    with connect() as conn:
        symbols = [s.strip().upper() for s in a.symbols.split(",")] if a.symbols else universe(conn, a.universe or "nifty500")
        if a.skip_existing:
            done = {r["symbol"] for r in conn.execute("SELECT DISTINCT symbol FROM fundamentals WHERE period_type = 'FY'")}
            symbols = [s for s in symbols if s not in done]

        nse = NseClient()
        ok = failed = streak = 0
        try:
            for i, symbol in enumerate(symbols, 1):
                try:
                    n = load_symbol(nse, conn, symbol, a.years, a.quarters)
                    ok += 1
                    streak = 0
                    print(f"[{i}/{len(symbols)}] {symbol}: {n} rows", flush=True)
                except Exception as e:  # keep going; one bad filing shouldn't stop the batch
                    conn.rollback()
                    failed += 1
                    streak += 1
                    print(f"[{i}/{len(symbols)}] {symbol}: FAILED {type(e).__name__}: {e}", flush=True)
                    if streak >= MAX_CONSECUTIVE_FAILURES:
                        raise SystemExit(f"Stopping: {streak} failures in a row (NSE is probably blocking this network).") from e
        finally:
            nse.close()
    print(f"done: {ok} ok, {failed} failed. Now run: python -m app.ingest.compute_metrics")


if __name__ == "__main__":
    main()
