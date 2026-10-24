"""Audit data shown on the live site against independent sources.

    python scripts/validate_live.py --api https://genscr-api.onrender.com --n 110 --out data/audit

Checks per stock (live API vs reference):
  * close / day change / turnover      vs NSE's official bhavcopy for the same date (parsed independently)
  * 52W high/low, returns, SMA, RSI     vs recomputation from the price history the site serves
  * market cap, P/E, P/B, ROE, D/E ...  vs recomputation from the financials the site serves
  * revenue, net profit (subset)        vs the company's own XBRL results filing on NSE
  * dividends, TTM yield, bonus/split   vs NSE corporate actions fetched fresh
  * total return                        invariants + cross-check with adjusted prices
  * missing data                        every displayed field, expected vs unexpected gaps
Network: throttled to stay under the API's per-IP rate limit and to be polite to NSE.
"""

import argparse
import csv
import io
import json
import math
import random
import re
import time
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
NSE = "https://www.nseindia.com"
ARCHIVE = "https://nsearchives.nseindia.com"
API_DELAY = 0.75  # < 90 requests/minute
NSE_DELAY = 1.5

MUST_INCLUDE = ["COALINDIA", "ITC", "TCS", "HDFCBANK", "RELIANCE", "INFY", "ETERNAL", "PCJEWELLER", "M&M", "SBIN",
                "ICICIBANK", "BAJFINANCE", "HINDUNILVR", "LT", "WIPRO", "VEDL", "ONGC", "NTPC", "TATASTEEL", "SUNPHARMA"]
DISPLAYED = ["close", "change_pct", "high_52w", "low_52w", "pct_from_52w_high", "return_1m", "return_1y", "avg_volume_20d",
             "turnover", "rsi_14", "sma_50", "sma_200", "market_cap", "pe", "pb", "roe", "roce", "debt_to_equity", "net_margin",
             "revenue_growth_yoy", "profit_growth_yoy", "piotroski_f", "altman_z", "dividend_yield"]
FUNDAMENTAL_FIELDS = {"market_cap", "pe", "pb", "roe", "roce", "debt_to_equity", "net_margin", "revenue_growth_yoy",
                      "profit_growth_yoy", "piotroski_f", "altman_z"}


class Audit:
    def __init__(self):
        self.results = defaultdict(lambda: {"pass": 0, "fail": 0, "skip": 0})
        self.failures: list[dict] = []
        self.gaps: dict[str, Counter] = defaultdict(Counter)

    def check(self, name: str, symbol: str, ok: bool | None, detail: str = ""):
        key = "skip" if ok is None else ("pass" if ok else "fail")
        self.results[name][key] += 1
        if ok is False:
            self.failures.append({"check": name, "symbol": symbol, "detail": detail})


def close_enough(a, b, abs_tol=0.0, rel_tol=0.0):
    if a is None or b is None:
        return False
    return math.isclose(float(a), float(b), abs_tol=abs_tol, rel_tol=rel_tol)


class Clients:
    def __init__(self, api: str):
        self.api = api.rstrip("/") + "/api"
        self.http = httpx.Client(timeout=120, headers={"User-Agent": UA})
        self.nse = httpx.Client(timeout=60, follow_redirects=True,
                                headers={"User-Agent": UA, "Referer": NSE + "/", "Accept": "application/json, */*"})
        try:
            self.nse.get(NSE)
        except httpx.HTTPError:
            pass

    def get(self, path: str):
        time.sleep(API_DELAY)
        for attempt in range(4):
            r = self.http.get(self.api + path)
            if r.status_code in (429, 502, 503, 504):
                time.sleep(15 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        r.raise_for_status()

    def post(self, path: str, body: dict):
        time.sleep(API_DELAY)
        r = self.http.post(self.api + path, json=body)
        r.raise_for_status()
        return r.json()

    def nse_json(self, path: str):
        time.sleep(NSE_DELAY)
        r = self.nse.get(NSE + path)
        r.raise_for_status()
        return r.json()

    def nse_bytes(self, url: str) -> bytes:
        time.sleep(NSE_DELAY)
        r = self.nse.get(url)
        r.raise_for_status()
        return r.content


# ---------- independent references ----------

def load_bhavcopy(c: Clients, d: date) -> dict[str, dict]:
    url = f"{ARCHIVE}/content/cm/BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
    with zipfile.ZipFile(io.BytesIO(c.nse_bytes(url))) as z:
        text = z.read(z.namelist()[0]).decode()
    out = {}
    for r in csv.DictReader(io.StringIO(text)):
        if r["Sgmt"] == "CM" and r["SctySrs"] in ("EQ", "BE", "BZ", "SM", "ST"):
            if r["TckrSymb"] not in out or r["SctySrs"] == "EQ":
                out[r["TckrSymb"]] = {"close": float(r["ClsPric"]), "prev": float(r["PrvsClsgPric"]),
                                      "turnover_cr": float(r["TtlTrfVal"]) / 1e7, "high": float(r["HghPric"]), "low": float(r["LwPric"])}
    return out


def nse_actions(c: Clients, symbol: str, start: date, end: date) -> list[dict]:
    path = (f"/api/corporates-corporateActions?index=equities&symbol={symbol.replace('&', '%26')}"
            f"&from_date={start:%d-%m-%Y}&to_date={end:%d-%m-%Y}")
    out = []
    for r in c.nse_json(path) or []:
        try:
            ex = datetime.strptime(r["exDate"].strip().title(), "%d-%b-%Y").date()
        except (KeyError, ValueError):
            continue
        out.append({"ex_date": ex, "subject": " ".join(r.get("subject", "").split()), "fv": r.get("faceVal")})
    return out


_RS = re.compile(r"(?:rs|re)\.?\s*([\d]+(?:\.\d+)?)", re.I)


def simple_dividend(subject: str) -> float | None:
    """Deliberately simple, independent reading: sum of 'Rs X' amounts on dividend lines, ignoring '(including ...)'."""
    s = re.split(r"\(?\s*including\b", subject, flags=re.I)[0]
    if not re.search(r"dividend|\bdiv\b|div[.\-]|intdiv", s, re.I) or re.search(r"sub-?division|split", s, re.I):
        return None
    amounts = [float(a) for a in _RS.findall(s)]
    return sum(amounts) if amounts else None


def xbrl_latest_fy(c: Clients, symbol: str) -> dict | None:
    data = c.nse_json(f"/api/integrated-filing-results?symbol={symbol.replace('&', '%26')}&type=Integrated%20Filing-%20Financials")
    rows = data.get("data", []) if isinstance(data, dict) else []
    march = [r for r in rows if r.get("qe_Date", "").upper().startswith("31-MAR") and r.get("xbrl")]
    if not march:
        return None
    march.sort(key=lambda r: (datetime.strptime(r["qe_Date"].title(), "%d-%b-%Y"), r.get("consolidated") == "Consolidated"), reverse=True)
    latest_fy = march[0]["qe_Date"]
    pick = next((r for r in march if r["qe_Date"] == latest_fy and r.get("consolidated") == "Consolidated"), march[0])
    xml = c.nse_bytes(pick["xbrl"]).decode("utf-8", "replace")

    def fact(*names):
        for n in names:
            m = re.search(rf"<[\w-]+:{n}\b[^>]*contextRef=\"FourD\"[^>]*>([-\d.]+)<", xml)
            if m:
                return float(m.group(1)) / 1e7
        return None

    return {"period_end": datetime.strptime(latest_fy.title(), "%d-%b-%Y").date().isoformat(),
            "consolidated": pick.get("consolidated"),
            "revenue": fact("RevenueFromOperations", "Income"),
            "net_profit": fact("ProfitOrLossAttributableToOwnersOfParent", "ProfitLossForPeriod",
                               "ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates", "ProfitLossForThePeriod")}


# ---------- recomputation helpers ----------

def rsi(closes, n=14):
    if len(closes) < n + 1:
        return None
    d = [b - a for a, b in zip(closes, closes[1:], strict=False)]
    g = sum(x for x in d[:n] if x > 0) / n
    lo = sum(-x for x in d[:n] if x < 0) / n
    for x in d[n:]:
        g = (g * (n - 1) + max(x, 0)) / n
        lo = (lo * (n - 1) + max(-x, 0)) / n
    return 100.0 if lo == 0 else 100 - 100 / (1 + g / lo)


def audit_stock(c: Clients, a: Audit, sym: str, bhav: dict, xbrl: bool, today: date):
    s = c.get(f"/stocks/{sym.replace('&', '%26')}")
    prices = c.get(f"/stocks/{sym.replace('&', '%26')}/prices?range=max")
    funds = c.get(f"/stocks/{sym.replace('&', '%26')}/fundamentals?period=FY&limit=6")
    divs = c.get(f"/stocks/{sym.replace('&', '%26')}/dividends")
    tl = c.get(f"/stocks/{sym.replace('&', '%26')}/timeline")
    facts = c.get(f"/stocks/{sym.replace('&', '%26')}/facts")
    tr = None
    try:
        tr = c.get(f"/stocks/{sym.replace('&', '%26')}/total-return?years=3&amount=10000")
    except httpx.HTTPStatusError:
        pass

    # --- missing data audit ---
    has_funds = bool(funds)
    latest = funds[0] if funds else None
    for f in DISPLAYED:
        if s.get(f) is not None:
            continue
        reason = "unexpected"
        if f in FUNDAMENTAL_FIELDS and not has_funds:
            reason = "no financials loaded (outside Nifty 500 coverage)"
        elif f == "pe" and latest and (latest.get("net_profit") or 0) <= 0:
            reason = "loss-making (P/E not meaningful)"
        elif f == "altman_z" and latest and latest.get("current_assets") is None:
            reason = "bank/financial (Altman not applicable)"
        elif f in ("piotroski_f", "revenue_growth_yoy", "profit_growth_yoy") and len(funds) < 2:
            reason = "only one year of financials"
        elif f == "profit_growth_yoy" and len(funds) > 1 and (funds[1].get("net_profit") or 0) <= 0:
            reason = "prior-year loss (growth not meaningful)"
        elif f == "piotroski_f" and latest and latest.get("cfo") is None:
            reason = "cash flow not in filing"
        elif f in ("sma_200", "rsi_14", "return_1y", "sma_50") and len(prices) < 260:
            reason = "short price history (new listing)"
        elif f in ("roce", "debt_to_equity", "net_margin", "pb", "roe") and latest:
            reason = "input missing in filing"
        a.gaps[f][reason] += 1
        a.check("no unexpected missing fields", sym, reason != "unexpected", f"{f} is null")

    # --- vs NSE bhavcopy ---
    b = bhav.get(sym)
    if b is None:
        a.check("close matches NSE bhavcopy", sym, None)
    else:
        a.check("close matches NSE bhavcopy", sym, close_enough(s["close"], b["close"], abs_tol=0.011), f"site {s['close']} vs NSE {b['close']}")
        exp = (b["close"] / b["prev"] - 1) * 100 if b["prev"] else None
        a.check("day change matches NSE", sym, close_enough(s["change_pct"], exp, abs_tol=0.02), f"site {s['change_pct']} vs NSE {exp:.2f}")
        a.check("turnover matches NSE", sym, close_enough(s["turnover"], b["turnover_cr"], abs_tol=0.02, rel_tol=0.001),
                f"site {s['turnover']} vs NSE {b['turnover_cr']:.2f}")

    # --- vs served price history ---
    if prices:
        last = prices[-1]
        a.check("chart ends on as-of date with same close", sym, last["time"] == s["as_of"] and close_enough(last["close"], s["close"], abs_tol=0.011),
                f"chart {last['time']} {last['close']} vs {s['as_of']} {s['close']}")
        closes = [p["close"] for p in prices]
        year = prices[-252:]
        a.check("52W high consistent with chart", sym, close_enough(s["high_52w"], max(p["high"] for p in year), abs_tol=0.011),
                f"{s['high_52w']} vs {max(p['high'] for p in year)}")
        a.check("52W low consistent with chart", sym, close_enough(s["low_52w"], min(p["low"] for p in year), abs_tol=0.011),
                f"{s['low_52w']} vs {min(p['low'] for p in year)}")
        if len(closes) > 252:
            r1y = (closes[-1] / closes[-253] - 1) * 100
            tol = 0.06 if closes[-253] >= 50 else 0.25  # 2-decimal chart prices on low-priced stocks
            a.check("1Y return consistent with chart", sym, close_enough(s["return_1y"], r1y, abs_tol=tol), f"{s['return_1y']} vs {r1y:.2f}")
        if len(closes) >= 200:
            a.check("200 DMA consistent with chart", sym, close_enough(s["sma_200"], sum(closes[-200:]) / 200, rel_tol=0.001),
                    f"{s['sma_200']} vs {sum(closes[-200:]) / 200:.2f}")
            a.check("RSI consistent with chart", sym, close_enough(s["rsi_14"], rsi(closes), abs_tol=0.1), f"{s['rsi_14']} vs {rsi(closes):.2f}")
        # gaps and unexplained jumps
        dates = [date.fromisoformat(p["time"]) for p in prices]
        recent = [(d1, d2) for d1, d2 in zip(dates, dates[1:], strict=False) if d2 >= today - timedelta(days=366)]
        big_gaps = [(str(x), str(y)) for x, y in recent if (y - x).days > 6]
        if big_gaps and len(big_gaps) >= 3 and all(7 <= (date.fromisoformat(y) - date.fromisoformat(x)).days <= 8 for x, y in big_gaps):
            a.check("no gaps over 6 days in last year", sym, None)  # weekly-only trading (periodic call auction) mirrors NSE
        else:
            a.check("no gaps over 6 days in last year", sym, not big_gaps, f"gaps {big_gaps[:3]}")
        demergers = {e["date"] for e in tl if e["kind"] == "demerger"}
        jumps = [(prices[i]["time"], round(closes[i] / closes[i - 1] - 1, 3)) for i in range(1, len(closes))
                 if closes[i - 1] and abs(closes[i] / closes[i - 1] - 1) > 0.4 and prices[i]["time"] not in demergers]
        a.check("no unexplained 40%+ daily jumps (missed split/bonus)", sym, not jumps, f"jumps {jumps[:3]}")

    # --- fundamentals recomputation ---
    if latest and s.get("market_cap") is not None:
        shares = latest.get("shares_outstanding")
        mcap = s["close"] * shares / 1e7 if shares else None
        a.check("market cap = price x shares", sym, close_enough(s["market_cap"], mcap, rel_tol=0.002), f"{s['market_cap']} vs {mcap}")
        np_ = latest.get("net_profit")
        if np_ and np_ > 0:
            a.check("P/E = market cap / net profit", sym, close_enough(s["pe"], s["market_cap"] / np_, rel_tol=0.005), f"{s['pe']} vs {s['market_cap'] / np_:.2f}")
        eq = latest.get("total_equity")
        if eq and eq > 0:
            a.check("P/B = market cap / equity", sym, close_enough(s["pb"], s["market_cap"] / eq, rel_tol=0.005), f"{s['pb']} vs {s['market_cap'] / eq:.2f}")
            a.check("D/E = debt / equity", sym, close_enough(s["debt_to_equity"], (latest.get("total_debt") or 0) / eq, abs_tol=0.006),
                    f"{s['debt_to_equity']} vs {(latest.get('total_debt') or 0) / eq:.2f}")
        if np_ is not None and latest.get("revenue"):
            a.check("net margin = profit / revenue", sym, close_enough(s["net_margin"], np_ / latest["revenue"] * 100, abs_tol=0.06),
                    f"{s['net_margin']} vs {np_ / latest['revenue'] * 100:.2f}")
        if len(funds) > 1 and funds[1].get("revenue") and latest.get("revenue"):
            g = (latest["revenue"] / funds[1]["revenue"] - 1) * 100
            a.check("revenue growth = YoY change", sym, close_enough(s["revenue_growth_yoy"], g, abs_tol=0.06), f"{s['revenue_growth_yoy']} vs {g:.2f}")
        # plausibility
        a.check("ratios in plausible ranges", sym,
                (s["pe"] is None or 0 < s["pe"] < 5000) and (s["roe"] is None or -500 < s["roe"] < 500)
                and (s["debt_to_equity"] is None or 0 <= s["debt_to_equity"] < 100), f"pe {s['pe']} roe {s['roe']} de {s['debt_to_equity']}")

    # --- vs company XBRL filing ---
    if xbrl and latest:
        ref = xbrl_latest_fy(c, sym)
        if ref is None:
            a.check("revenue matches XBRL filing", sym, None)
        elif ref["period_end"] != latest["period_end"]:
            a.check("latest FY matches newest filing", sym, False, f"site FY {latest['period_end']} vs filing {ref['period_end']}")
        else:
            a.check("latest FY matches newest filing", sym, True)
            a.check("revenue matches XBRL filing", sym, close_enough(latest["revenue"], ref["revenue"], rel_tol=0.002),
                    f"site {latest['revenue']} vs filing {ref['revenue']}")
            a.check("net profit matches XBRL filing", sym, close_enough(latest["net_profit"], ref["net_profit"], rel_tol=0.002, abs_tol=0.02),
                    f"site {latest['net_profit']} vs filing {ref['net_profit']}")

    # --- vs NSE corporate actions ---
    end = date.fromisoformat(s["as_of"])
    nse = nse_actions(c, sym, date(2005, 1, 1), end)
    ttm_start = date(end.year - 1, end.month, min(end.day, 28))
    per_day = defaultdict(float)  # NSE sometimes lists a final and a special dividend as separate records
    for x in nse:
        amt = simple_dividend(x["subject"])
        if amt:
            per_day[x["ex_date"]] += amt
    nse_divs = sorted(per_day.items())
    site_pay = {(p["ex_date"]): p["amount"] for p in divs["payments"]}
    window = [d for d in nse_divs if d[0] >= end - timedelta(days=5 * 365)]
    missing = [(str(d), amt) for d, amt in window if str(d) not in site_pay]
    a.check("every NSE dividend (5y) is shown", sym, not missing, f"missing {missing[:4]}")
    mism = [(str(d), amt, site_pay[str(d)]) for d, amt in window if str(d) in site_pay and not close_enough(site_pay[str(d)], amt, abs_tol=0.011)]
    a.check("dividend amounts match NSE (5y)", sym, not mism, f"(date, NSE, site) {mism[:4]}")
    has_bonus_split = any(re.search(r"bonus|split|sub-?division", x["subject"], re.I) for x in nse if x["ex_date"] > ttm_start)
    if not has_bonus_split:
        ttm = sum(amt for d, amt in nse_divs if ttm_start < d <= end)
        exp_y = ttm / s["close"] * 100 if s["close"] else None
        a.check("TTM dividend yield matches NSE payments", sym, close_enough(s["dividend_yield"], exp_y, abs_tol=0.02),
                f"site {s['dividend_yield']} vs NSE {exp_y:.2f}")
    nse_events = {x["ex_date"].isoformat() for x in nse
                  if re.search(r"bonus|split|sub-?division", x["subject"], re.I) and not re.search(r"debenture", x["subject"], re.I)}
    tl_events = {e["date"] for e in tl if e["kind"] in ("bonus", "split")}
    a.check("timeline shows every NSE bonus/split", sym, nse_events <= tl_events, f"missing {sorted(nse_events - tl_events)[:4]}")
    a.check("dividend stats internally consistent", sym, divs["stats"]["total_payments"] == len(divs["payments"])
            and abs(sum(y["declared"] for y in divs["years"]) - sum(p["amount"] for p in divs["payments"])) < 0.05)

    # --- total return ---
    if tr:
        diff = tr["with_dividends"]["total_value"] - tr["price_only"]["total_value"]
        a.check("total return: with-dividends = price-only + dividends", sym, close_enough(diff, tr["dividends_received"], abs_tol=1.0),
                f"{diff:.2f} vs {tr['dividends_received']}")
        p0 = next((p for p in prices if p["time"] >= tr["start_date"]), None)
        if p0 and p0["close"]:
            exp_v = 10000 * prices[-1]["close"] / p0["close"]
            a.check("total return: price-only matches adjusted chart", sym, close_enough(tr["price_only"]["total_value"], exp_v, rel_tol=0.01),
                    f"{tr['price_only']['total_value']} vs {exp_v:.0f}")
        a.check("total return: reinvested within sane range of cash", sym,
                0.7 < tr["reinvested"]["total_value"] / max(tr["with_dividends"]["total_value"], 1) < 1.3)

    # --- facts ---
    a.check("every fact cites a source", sym, all(f.get("source") for f in facts))
    ppd = next((f for f in facts if f["id"] == "profit_per_day"), None)
    if ppd and latest and latest.get("net_profit"):
        m = re.search(r"₹([\d,.]+) Cr of profit", ppd["text"])
        exp_p = latest["net_profit"] / 365
        a.check("'profit per day' fact = FY profit / 365", sym, bool(m) and close_enough(float(m.group(1).replace(",", "")), exp_p, rel_tol=0.01, abs_tol=0.06),
                f"{m.group(1) if m else None} vs {exp_p:.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="https://genscr-api.onrender.com")
    ap.add_argument("--n", type=int, default=110)
    ap.add_argument("--xbrl", type=int, default=30, help="how many stocks to check against XBRL filings")
    ap.add_argument("--out", default="data/audit")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    c = Clients(args.api)
    a = Audit()
    universe = c.post("/screener", {"query": "turnover > 0", "sort": "turnover", "order": "desc", "limit": 500})["results"]
    with_f = [u["symbol"] for u in universe if u.get("market_cap") is not None]
    without_f = [u["symbol"] for u in universe if u.get("market_cap") is None]
    rng = random.Random(args.seed)
    picks = list(dict.fromkeys(MUST_INCLUDE + rng.sample(with_f, min(len(with_f), int(args.n * 0.65)))
                               + rng.sample(without_f, min(len(without_f), int(args.n * 0.25)))))[: args.n]
    as_of = date.fromisoformat(c.get("/stocks/COALINDIA")["as_of"])
    bhav = load_bhavcopy(c, as_of)
    print(f"Auditing {len(picks)} stocks as of {as_of} against NSE bhavcopy ({len(bhav)} symbols)", flush=True)

    xbrl_set = set([p for p in picks if p in with_f][: args.xbrl])
    errors = []
    for i, sym in enumerate(picks, 1):
        try:
            audit_stock(c, a, sym, bhav, sym in xbrl_set, as_of)
            print(f"[{i}/{len(picks)}] {sym} ok", flush=True)
        except Exception as e:  # keep auditing others
            errors.append({"symbol": sym, "error": f"{type(e).__name__}: {e}"})
            print(f"[{i}/{len(picks)}] {sym} ERROR {e}", flush=True)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {"as_of": as_of.isoformat(), "stocks": len(picks), "symbols": picks, "results": a.results,
              "failures": a.failures, "gaps": {k: dict(v) for k, v in a.gaps.items()}, "errors": errors}
    (out / "audit.json").write_text(json.dumps(report, indent=2, default=str))
    total_pass = sum(r["pass"] for r in a.results.values())
    total_fail = sum(r["fail"] for r in a.results.values())
    print(f"\n=== {total_pass} passed, {total_fail} failed, {len(errors)} errors ===")
    for name, r in sorted(a.results.items(), key=lambda kv: -kv[1]["fail"]):
        print(f"{'FAIL' if r['fail'] else ' ok '}  {name:58} pass {r['pass']:4}  fail {r['fail']:3}  skip {r['skip']:3}")


if __name__ == "__main__":
    main()
