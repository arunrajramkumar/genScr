"use client";

import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { ArrowDownUp, Radar, Sparkles } from "lucide-react";
import { LINE_COLORS } from "./chartColors";
import { SectionNote } from "./Legal";
import { Loading } from "./ui";
import { api } from "@/lib/api";
import { fmtField, toNum } from "@/lib/format";
import type { RanksResponse, Stock, TotalReturnResponse } from "@/lib/types";

// Metrics for the highest/lowest table: field, label, unit.
const METRICS: [keyof Stock, string, string][] = [
  ["pe", "P/E", "x"], ["pb", "P/B", "x"], ["roe", "ROE", "%"], ["net_margin", "Net margin", "%"],
  ["revenue_growth_yoy", "Revenue growth", "%"], ["debt_to_equity", "Debt / equity", "x"],
  ["dividend_yield", "Dividend yield", "%"], ["return_1y", "1-year return", "%"],
];

const AXES: { field: string; label: string }[] = [
  { field: "roe", label: "ROE" },
  { field: "net_margin", label: "Margin" },
  { field: "revenue_growth_yoy", label: "Growth" },
  { field: "pe", label: "P/E" },
  { field: "debt_to_equity", label: "Debt/equity" },
  { field: "dividend_yield", label: "Yield" },
  { field: "return_1y", label: "1Y return" },
];

/** Highest and lowest value per metric: facts, with no view on which end is preferable. */
function extremes(stocks: Stock[]) {
  return METRICS.map(([field, label, unit]) => {
    const vals = stocks.map((s) => ({ s: s.symbol, v: toNum(s[field] as never) }))
      .filter((x) => x.v !== null && !(field === "pe" && (x.v as number) <= 0)) as { s: string; v: number }[];
    if (vals.length < 2) return { label, unit, high: null, low: null };
    const sorted = [...vals].sort((a, b) => b.v - a.v);
    const high = sorted[0], low = sorted[sorted.length - 1];
    return high.v === low.v ? { label, unit, high: null, low: null } : { label, unit, high, low };
  });
}

function RadarChart({ series }: { series: { symbol: string; values: (number | null)[] }[] }) {
  const size = 300, c = size / 2, r = 110, n = AXES.length;
  const pt = (i: number, v: number) => {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2;
    return [c + Math.cos(a) * r * (v / 100), c + Math.sin(a) * r * (v / 100)];
  };
  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="mx-auto w-full max-w-[340px]" role="img" aria-label="Percentile radar chart">
      {[25, 50, 75, 100].map((g) => (
        <polygon key={g} points={AXES.map((_, i) => pt(i, g).join(",")).join(" ")} fill="none" stroke="rgba(255,255,255,0.07)" />
      ))}
      {AXES.map((ax, i) => {
        const [x, y] = pt(i, 100);
        const [lx, ly] = pt(i, 122);
        return (
          <g key={ax.field}>
            <line x1={c} y1={c} x2={x} y2={y} stroke="rgba(255,255,255,0.07)" />
            <text x={lx} y={ly} fill="#7d8aa0" fontSize="10" textAnchor="middle" dominantBaseline="middle">{ax.label}</text>
          </g>
        );
      })}
      {series.map((s, si) => (
        <polygon
          key={s.symbol}
          points={s.values.map((v, i) => pt(i, v ?? 0).join(",")).join(" ")}
          fill={LINE_COLORS[si % LINE_COLORS.length]}
          fillOpacity={0.12}
          stroke={LINE_COLORS[si % LINE_COLORS.length]}
          strokeWidth={2}
        />
      ))}
    </svg>
  );
}

export default function CompareInsights({ stocks }: { stocks: Stock[] }) {
  const symbols = stocks.map((s) => s.symbol);
  const key = symbols.join(",");
  const [ranks, setRanks] = useState<Record<string, RanksResponse>>({});
  const [years, setYears] = useState(5);
  const [returns, setReturns] = useState<Record<string, TotalReturnResponse | null> | null>(null);

  useEffect(() => {
    Promise.all(symbols.map((s) => api<RanksResponse>(`/stocks/${encodeURIComponent(s)}/ranks`).then((r) => [s, r] as const).catch(() => [s, null] as const)))
      .then((rows) => setRanks(Object.fromEntries(rows.filter((r) => r[1]).map((r) => [r[0], r[1] as RanksResponse]))));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    setReturns(null);
    Promise.all(symbols.map((s) => api<TotalReturnResponse>(`/stocks/${encodeURIComponent(s)}/total-return?years=${years}&amount=10000`)
      .then((r) => [s, r] as const).catch(() => [s, null] as const)))
      .then((rows) => setReturns(Object.fromEntries(rows)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, years]);

  const ends = useMemo(() => extremes(stocks), [stocks]);
  const radar = symbols.map((s) => ({
    symbol: s,
    values: AXES.map((ax) => ranks[s]?.metrics.find((m) => m.field === ax.field)?.market_percentile ?? null),
  }));
  const maxValue = Math.max(1, ...Object.values(returns ?? {}).map((r) => r?.reinvested.total_value ?? 0));
  const colorOf = (s: string) => LINE_COLORS[symbols.indexOf(s) % LINE_COLORS.length];

  return (
    <div className="space-y-4">
      <section className="panel p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-gold" />
            <h2 className="text-lg font-semibold text-white">₹10,000 invested {years} year{years > 1 ? "s" : ""} ago, dividends included</h2>
          </div>
          <div className="seg">
            {[1, 3, 5].map((y) => (
              <button key={y} onClick={() => setYears(y)} className={clsx("seg-btn", years === y && "seg-btn-active")}>{y}Y</button>
            ))}
          </div>
        </div>
        {!returns && <Loading />}
        {returns && (
          <div className="mt-4 space-y-3">
            {[...symbols].sort((a, b) => (returns[b]?.reinvested.total_value ?? -1) - (returns[a]?.reinvested.total_value ?? -1)).map((s) => {
              const r = returns[s];
              return (
                <div key={s}>
                  <div className="flex items-baseline justify-between text-sm">
                    <span className="font-medium text-white">{s}</span>
                    {r ? (
                      <span className="num text-white">
                        ₹{Math.round(r.reinvested.total_value).toLocaleString("en-IN")}
                        <span className={clsx("ml-2 text-xs", (r.reinvested.cagr ?? 0) >= 0 ? "text-up" : "text-down")}>
                          {r.reinvested.cagr !== null ? `${r.reinvested.cagr > 0 ? "+" : ""}${r.reinvested.cagr.toFixed(1)}% p.a.` : ""}
                        </span>
                      </span>
                    ) : <span className="text-xs text-muted">not enough history</span>}
                  </div>
                  {r && (
                    <>
                      <div className="mt-1 h-3 overflow-hidden rounded-full bg-white/5">
                        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${(r.reinvested.total_value / maxValue) * 100}%`, background: colorOf(s) }} />
                      </div>
                      <div className="mt-0.5 text-[11px] text-muted">
                        Price only ₹{Math.round(r.price_only.total_value).toLocaleString("en-IN")} · dividends ₹{Math.round(r.dividends_received).toLocaleString("en-IN")}
                        {r.bonus_split_shares > 0 && " · includes bonus/split shares"}
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="panel p-5">
          <div className="mb-2 flex items-center gap-2">
            <Radar className="h-5 w-5 text-accent" />
            <h2 className="text-lg font-semibold text-white">Percentile profile</h2>
          </div>
          {Object.keys(ranks).length ? <RadarChart series={radar} /> : <Loading />}
          <div className="mt-2 flex flex-wrap justify-center gap-3 text-xs">
            {symbols.map((s) => (
              <span key={s} className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: colorOf(s) }} />{s}</span>
            ))}
          </div>
          <p className="mt-2 text-center text-[11px] text-muted">Each axis: share of NSE stocks with a lower value (centre = lowest, outer edge = highest). Further out is not better or worse.</p>
        </section>

        <section className="panel p-5">
          <div className="mb-3 flex items-center gap-2">
            <ArrowDownUp className="h-5 w-5 text-accent" />
            <h2 className="text-lg font-semibold text-white">Highest and lowest, metric by metric</h2>
          </div>
          <ul className="space-y-2">
            {ends.map((e) => (
              <li key={e.label} className="grid grid-cols-[minmax(0,7rem)_1fr_1fr] items-center gap-3 rounded-xl border border-white/[0.06] bg-black/25 px-3 py-2 text-xs">
                <span className="text-sm text-slate-300">{e.label}</span>
                {e.high && e.low ? (
                  <>
                    <span className="min-w-0"><span className="block text-[10px] uppercase tracking-wider text-muted">Highest</span>
                      <span className="inline-flex items-center gap-1.5 text-white"><span className="h-2 w-2 shrink-0 rounded-full" style={{ background: colorOf(e.high.s) }} />{e.high.s} <span className="num text-slate-300">{fmtField(e.high.v, e.unit)}</span></span></span>
                    <span className="min-w-0"><span className="block text-[10px] uppercase tracking-wider text-muted">Lowest</span>
                      <span className="inline-flex items-center gap-1.5 text-white"><span className="h-2 w-2 shrink-0 rounded-full" style={{ background: colorOf(e.low.s) }} />{e.low.s} <span className="num text-slate-300">{fmtField(e.low.v, e.unit)}</span></span></span>
                  </>
                ) : <span className="col-span-2 text-muted">Not enough data</span>}
              </li>
            ))}
          </ul>
        </section>
      </div>
      <SectionNote>
        Highest and lowest show the numerically larger and smaller figure only; neither end is better. Returns are historical, from NSE prices and
        recorded corporate actions, with dividends reinvested. None of this is a ranking or a recommendation.
      </SectionNote>
    </div>
  );
}
