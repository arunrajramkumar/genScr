"use client";

import { useEffect, useState } from "react";
import { Gauge } from "lucide-react";
import { SectionNote } from "./Legal";
import { Loading } from "./ui";
import { api } from "@/lib/api";
import { fmtPct } from "@/lib/format";

interface Pulse {
  as_of: string | null;
  market: {
    stocks: number; above_50: number; has_50: number; above_200: number; has_200: number;
    rsi_above_70: number; rsi_below_30: number; has_rsi: number;
    off_0_5: number; off_5_20: number; off_20_40: number; off_40_plus: number;
    up_1y: number; has_1y: number; median_return_1y: number | null; median_from_high: number | null;
  } | null;
  sectors: { sector: string; stocks: number; pct_above_200: number | null; pct_above_50: number | null; median_from_high: number | null }[];
}

const pct = (a: number, b: number) => (b ? (a / b) * 100 : 0);

/** Half-ring gauge: the share of stocks meeting a condition. Neutral colour, it describes the market, not a signal. */
function Ring({ value, label, sub }: { value: number; label: string; sub: string }) {
  const r = 42, c = Math.PI * r;
  return (
    <div className="flex flex-col items-center rounded-xl border border-white/[0.06] bg-black/25 p-3">
      <svg viewBox="0 0 100 56" className="w-full max-w-[150px]" aria-hidden>
        <path d="M8 50 A42 42 0 0 1 92 50" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="8" strokeLinecap="round" />
        <path d="M8 50 A42 42 0 0 1 92 50" fill="none" stroke="url(#pulse-g)" strokeWidth="8" strokeLinecap="round" strokeDasharray={`${(value / 100) * c} ${c}`} />
        <defs><linearGradient id="pulse-g" x1="0" x2="1"><stop offset="0" stopColor="#7c9cff" /><stop offset="1" stopColor="#22d3ee" /></linearGradient></defs>
      </svg>
      <div className="num -mt-5 text-xl font-semibold text-white">{Math.round(value)}%</div>
      <div className="mt-1 text-center text-xs text-slate-300">{label}</div>
      <div className="text-center text-[10px] text-muted">{sub}</div>
    </div>
  );
}

export default function MarketPulse() {
  const [data, setData] = useState<Pulse | null>(null);
  useEffect(() => { api<Pulse>("/market/pulse").then(setData).catch(() => setData({ as_of: null, market: null, sectors: [] })); }, []);
  if (!data) return <Loading />;
  const m = data.market;
  if (!m) return null;
  const offTotal = m.off_0_5 + m.off_5_20 + m.off_20_40 + m.off_40_plus;
  const buckets: [string, number, string][] = [
    ["Within 5%", m.off_0_5, "#22d3ee"], ["5–20% below", m.off_5_20, "#7c9cff"],
    ["20–40% below", m.off_20_40, "#a78bfa"], ["40%+ below", m.off_40_plus, "#f472b6"],
  ];
  return (
    <section className="panel p-5">
      <div className="mb-1 flex items-center gap-2"><Gauge className="h-5 w-5 text-cyan-400" /><h2 className="text-lg font-semibold text-white">Market pulse</h2></div>
      <p className="mb-4 text-xs text-muted">How the whole NSE equity market is placed today, across {m.stocks.toLocaleString("en-IN")} stocks.</p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Ring value={pct(m.above_200, m.has_200)} label="above their 200-day average" sub={`${m.above_200.toLocaleString("en-IN")} of ${m.has_200.toLocaleString("en-IN")}`} />
        <Ring value={pct(m.above_50, m.has_50)} label="above their 50-day average" sub={`${m.above_50.toLocaleString("en-IN")} of ${m.has_50.toLocaleString("en-IN")}`} />
        <Ring value={pct(m.up_1y, m.has_1y)} label="higher than a year ago" sub={`median 1Y return ${fmtPct(m.median_return_1y)}`} />
        <div className="rounded-xl border border-white/[0.06] bg-black/25 p-3">
          <div className="text-xs text-slate-300">Distance from 52-week high</div>
          <div className="mt-2 flex h-3 overflow-hidden rounded-full">
            {buckets.map(([l, n, c]) => <div key={l} title={`${l}: ${n}`} style={{ width: `${pct(n, offTotal)}%`, background: c }} />)}
          </div>
          <ul className="mt-2 space-y-0.5 text-[11px]">
            {buckets.map(([l, n, c]) => (
              <li key={l} className="flex justify-between"><span className="inline-flex items-center gap-1.5 text-slate-300"><span className="h-2 w-2 rounded-full" style={{ background: c }} />{l}</span><span className="num text-muted">{Math.round(pct(n, offTotal))}%</span></li>
            ))}
          </ul>
          <div className="mt-1 text-[10px] text-muted">Median stock: {fmtPct(m.median_from_high)} from its high · RSI above 70: {m.rsi_above_70}, below 30: {m.rsi_below_30}</div>
        </div>
      </div>

      {data.sectors.length > 0 && (
        <div className="mt-5">
          <div className="label mb-2">By sector: share of stocks above their 200-day average</div>
          <ul className="grid gap-x-6 gap-y-1.5 md:grid-cols-2">
            {data.sectors.map((s) => (
              <li key={s.sector} className="grid grid-cols-[minmax(0,10rem)_1fr_auto] items-center gap-2 text-xs">
                <span className="truncate text-slate-300" title={s.sector}>{s.sector}</span>
                <div className="h-2 overflow-hidden rounded-full bg-white/[0.05]">
                  <div className="h-full rounded-full bg-gradient-to-r from-accent/70 to-cyan-400/70" style={{ width: `${s.pct_above_200 ?? 0}%` }} />
                </div>
                <span className="num w-24 text-right text-muted"><span className="text-white">{s.pct_above_200 ?? "—"}%</span> of {s.stocks}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="mt-4"><SectionNote>Counts of stocks meeting each condition on the latest trading day. A description of the market, not a forecast or a signal.</SectionNote></div>
    </section>
  );
}
