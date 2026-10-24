"use client";

import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { Flag, Radar, Sparkles } from "lucide-react";
import { LINE_COLORS } from "./chartColors";
import { SectionNote } from "./Legal";
import { Loading } from "./ui";
import { api } from "@/lib/api";
import { toNum } from "@/lib/format";
import type { RanksResponse, Stock, TotalReturnResponse } from "@/lib/types";

const CATEGORIES: { name: string; fields: [keyof Stock, boolean][] }[] = [
  { name: "Valuation", fields: [["pe", false], ["pb", false]] },
  { name: "Profitability", fields: [["roe", true], ["roce", true], ["net_margin", true]] },
  { name: "Growth", fields: [["revenue_growth_yoy", true], ["profit_growth_yoy", true]] },
  { name: "Balance sheet", fields: [["debt_to_equity", false], ["altman_z", true], ["piotroski_f", true]] },
  { name: "Income", fields: [["dividend_yield", true]] },
  { name: "Momentum", fields: [["return_1y", true], ["pct_from_52w_high", true]] },
];

const AXES: { field: string; label: string }[] = [
  { field: "roe", label: "ROE" },
  { field: "net_margin", label: "Margin" },
  { field: "revenue_growth_yoy", label: "Growth" },
  { field: "pe", label: "Low P/E" },
  { field: "debt_to_equity", label: "Low debt" },
  { field: "dividend_yield", label: "Yield" },
  { field: "return_1y", label: "1Y return" },
];

/** Which stock has the more favourable value on most metrics of each category (factual, per metric). */
function categoryLeads(stocks: Stock[]) {
  return CATEGORIES.map((c) => {
    const wins = new Map<string, string[]>();
    for (const [field, hib] of c.fields) {
      const vals = stocks
        .map((s) => ({ s: s.symbol, v: toNum(s[field] as never) }))
        .filter((x) => x.v !== null && !(field === "pe" && (x.v as number) <= 0)) as { s: string; v: number }[];
      if (vals.length < 2) continue;
      const best = vals.reduce((a, b) => ((hib ? b.v > a.v : b.v < a.v) ? b : a));
      wins.set(best.s, [...(wins.get(best.s) ?? []), String(field)]);
    }
    const ranked = Array.from(wins.entries()).sort((a, b) => b[1].length - a[1].length);
    const total = c.fields.length;
    if (!ranked.length) return { name: c.name, leader: null, detail: "Not enough data" };
    const [leader, fields] = ranked[0];
    const tie = ranked[1] && ranked[1][1].length === fields.length;
    return { name: c.name, leader: tie ? null : leader, detail: tie ? "Split between stocks" : `ahead on ${fields.length} of ${total} metric${total > 1 ? "s" : ""}` };
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

  const leads = useMemo(() => categoryLeads(stocks), [stocks]);
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
            <h2 className="text-lg font-semibold text-white">Strength profile</h2>
          </div>
          {Object.keys(ranks).length ? <RadarChart series={radar} /> : <Loading />}
          <div className="mt-2 flex flex-wrap justify-center gap-3 text-xs">
            {symbols.map((s) => (
              <span key={s} className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: colorOf(s) }} />{s}</span>
            ))}
          </div>
          <p className="mt-2 text-center text-[11px] text-muted">Each axis: percentile among all NSE stocks (outer edge = ahead of all).</p>
        </section>

        <section className="panel p-5">
          <div className="mb-3 flex items-center gap-2">
            <Flag className="h-5 w-5 text-up" />
            <h2 className="text-lg font-semibold text-white">Category leads, metric by metric</h2>
          </div>
          <ul className="space-y-2.5">
            {leads.map((l) => (
              <li key={l.name} className="flex items-center justify-between gap-3 rounded-xl border border-white/[0.06] bg-black/25 px-3 py-2">
                <span className="text-sm text-slate-300">{l.name}</span>
                <span className="text-right text-sm">
                  {l.leader ? (
                    <span className="inline-flex items-center gap-1.5 font-semibold text-white">
                      <span className="h-2 w-2 rounded-full" style={{ background: colorOf(l.leader) }} />{l.leader}
                    </span>
                  ) : <span className="text-muted">—</span>}
                  <span className="block text-[11px] text-muted">{l.detail}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>
      <SectionNote>
        Category leads count which stock has the more favourable value on each listed metric. Returns are historical, from NSE prices and
        recorded corporate actions, with dividends reinvested. None of this is a ranking or a recommendation.
      </SectionNote>
    </div>
  );
}
