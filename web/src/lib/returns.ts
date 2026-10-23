import type { Candle } from "./types";

const DAY = 86_400_000;
const YEAR_DAYS = 365.25;

export interface Point { time: string; invested: number; value: number }

export interface InvestResult {
  invested: number;
  value: number;
  gain: number;
  gainPct: number;
  cagr: number | null; // % per year (XIRR for SIP)
  years: number;
  startDate: string;
  series: Point[];
}

const ts = (d: string) => new Date(d + "T00:00:00Z").getTime();

/** Whole years of history available. */
export function availableYears(prices: Candle[]): number {
  if (prices.length < 2) return 0;
  return Math.floor((ts(prices[prices.length - 1].time) - ts(prices[0].time)) / DAY / YEAR_DAYS + 0.02);
}

function sliceFrom(prices: Candle[], years: number): Candle[] {
  const end = ts(prices[prices.length - 1].time);
  const start = end - years * YEAR_DAYS * DAY;
  const i = prices.findIndex((p) => ts(p.time) >= start);
  return i < 0 ? [] : prices.slice(i);
}

export function lumpsum(prices: Candle[], years: number, amount: number): InvestResult | null {
  const pts = sliceFrom(prices, years);
  if (pts.length < 2 || !pts[0].close) return null;
  const units = amount / pts[0].close;
  const last = pts[pts.length - 1];
  const value = units * last.close;
  const span = (ts(last.time) - ts(pts[0].time)) / DAY / YEAR_DAYS;
  return {
    invested: amount,
    value,
    gain: value - amount,
    gainPct: (value / amount - 1) * 100,
    cagr: span > 0.5 ? (Math.pow(value / amount, 1 / span) - 1) * 100 : null,
    years: span,
    startDate: pts[0].time,
    series: pts.map((p) => ({ time: p.time, invested: amount, value: units * p.close })),
  };
}

/** Monthly SIP on the first trading day of each month. */
export function sip(prices: Candle[], years: number, monthly: number): InvestResult | null {
  const pts = sliceFrom(prices, years);
  if (pts.length < 2) return null;
  let units = 0, invested = 0, lastMonth = "";
  const flows: { t: number; amt: number }[] = [];
  const series: Point[] = [];
  for (const p of pts) {
    const month = p.time.slice(0, 7);
    if (month !== lastMonth && p.close) {
      units += monthly / p.close;
      invested += monthly;
      flows.push({ t: ts(p.time), amt: -monthly });
      lastMonth = month;
    }
    series.push({ time: p.time, invested, value: units * p.close });
  }
  const last = pts[pts.length - 1];
  const value = units * last.close;
  flows.push({ t: ts(last.time), amt: value });
  const irr = xirr(flows);
  return {
    invested,
    value,
    gain: value - invested,
    gainPct: (value / invested - 1) * 100,
    cagr: irr === null ? null : irr * 100,
    years: (ts(last.time) - ts(pts[0].time)) / DAY / YEAR_DAYS,
    startDate: pts[0].time,
    series,
  };
}

/** Annualised internal rate of return for dated cash flows (bisection; robust for SIPs). */
export function xirr(flows: { t: number; amt: number }[]): number | null {
  if (flows.length < 2) return null;
  const t0 = flows[0].t;
  const npv = (r: number) => flows.reduce((s, f) => s + f.amt / Math.pow(1 + r, (f.t - t0) / DAY / YEAR_DAYS), 0);
  let lo = -0.99, hi = 10;
  let fLo = npv(lo), fHi = npv(hi);
  if (fLo * fHi > 0) return null;
  for (let i = 0; i < 200; i++) {
    const mid = (lo + hi) / 2;
    const fMid = npv(mid);
    if (Math.abs(fMid) < 1e-6) return mid;
    if (fLo * fMid < 0) { hi = mid; fHi = fMid; } else { lo = mid; fLo = fMid; }
  }
  return (lo + hi) / 2;
}

/** Annualised volatility (%) of daily log returns over the last `years`. */
export function volatility(prices: Candle[], years = 3): number | null {
  const pts = sliceFrom(prices, Math.min(years, availableYears(prices) || 1));
  if (pts.length < 60) return null;
  const rets: number[] = [];
  for (let i = 1; i < pts.length; i++) if (pts[i - 1].close && pts[i].close) rets.push(Math.log(pts[i].close / pts[i - 1].close));
  const mean = rets.reduce((a, b) => a + b, 0) / rets.length;
  const variance = rets.reduce((a, b) => a + (b - mean) ** 2, 0) / (rets.length - 1);
  return Math.sqrt(variance * 252) * 100;
}

export function priceCagr(prices: Candle[], years: number): number | null {
  return lumpsum(prices, years, 1)?.cagr ?? null;
}

export interface Scenario { name: "Bear" | "Base" | "Bull"; cagr: number; value: number }

export interface Outlook {
  scenarios: Scenario[];
  priceCagr: number | null;
  priceYears: number;
  profitCagr: number | null;
  profitYears: number;
  vol: number | null;
  confidence: "low" | "medium" | "high";
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/**
 * Illustrative 5-year scenarios, NOT a forecast:
 *  base = average of (historical price CAGR, net-profit CAGR at a constant P/E)
 *  bear/bull = base -/+ annual volatility / sqrt(5)  (≈1σ range of a 5-year CAGR)
 */
export function outlook(prices: Candle[], fyProfits: { period_end: string; net_profit: number | null }[], amount = 10_000, horizon = 5): Outlook | null {
  const yrs = availableYears(prices);
  const priceYears = Math.min(5, yrs);
  const pc = priceYears >= 1 ? priceCagr(prices, priceYears) : null;

  const fy = fyProfits.filter((f) => f.net_profit !== null).sort((a, b) => a.period_end.localeCompare(b.period_end));
  let profitCagr: number | null = null, profitYears = 0;
  if (fy.length >= 2) {
    const first = fy[0], last = fy[fy.length - 1];
    profitYears = Math.round((ts(last.period_end) - ts(first.period_end)) / DAY / YEAR_DAYS);
    if (first.net_profit! > 0 && last.net_profit! > 0 && profitYears > 0) {
      profitCagr = clamp((Math.pow(last.net_profit! / first.net_profit!, 1 / profitYears) - 1) * 100, -30, 50);
    }
  }

  const inputs = [pc, profitCagr].filter((v): v is number => v !== null);
  if (!inputs.length) return null;
  const base = clamp(inputs.reduce((a, b) => a + b, 0) / inputs.length, -25, 40);
  const vol = volatility(prices);
  const band = vol !== null ? vol / Math.sqrt(horizon) : Math.abs(base) * 0.5 + 5;
  const mk = (name: Scenario["name"], r: number): Scenario => ({ name, cagr: r, value: amount * Math.pow(1 + r / 100, horizon) });

  return {
    scenarios: [mk("Bear", Math.max(base - band, -60)), mk("Base", base), mk("Bull", base + band)],
    priceCagr: pc,
    priceYears,
    profitCagr,
    profitYears,
    vol,
    confidence: inputs.length === 2 && priceYears >= 5 ? "high" : inputs.length === 2 || priceYears >= 3 ? "medium" : "low",
  };
}

/** Simple moving average aligned to input (null until enough points). */
export function movingAverage(prices: Candle[], n: number): { time: string; value: number }[] {
  const out: { time: string; value: number }[] = [];
  let sum = 0;
  for (let i = 0; i < prices.length; i++) {
    sum += prices[i].close;
    if (i >= n) sum -= prices[i - n].close;
    if (i >= n - 1) out.push({ time: prices[i].time, value: sum / n });
  }
  return out;
}
