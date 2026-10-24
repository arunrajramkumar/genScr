"use client";

import clsx from "clsx";
import { Activity, CalendarClock, GitCompareArrows, Lightbulb, Waves } from "lucide-react";
import { LINE_COLORS } from "./chartColors";
import { fmtCr, fmtPct, fmtPrice, toNum } from "@/lib/format";
import type { CompareResponse, Stock } from "@/lib/types";

type Data = CompareResponse;
const color = (i: number) => LINE_COLORS[i % LINE_COLORS.length];
const mon = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { month: "short", year: "numeric" });
const day = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
const num = (s: Stock, k: keyof Stock) => toNum(s[k] as never);
// Literal class names so Tailwind keeps them: one column per stock on wide screens.
const LG_COLS: Record<number, string> = { 2: "lg:grid-cols-2", 3: "lg:grid-cols-3", 4: "lg:grid-cols-4", 5: "lg:grid-cols-5" };

/** One card per stock: price, day move, size, and where today's price sits in its 52-week range. */
export function Snapshot({ data }: { data: Data }) {
  return (
    <div className={clsx("grid gap-3 sm:grid-cols-2", LG_COLS[data.stocks.length])}>
      {data.stocks.map((s, i) => {
        const close = num(s, "close"), lo = num(s, "low_52w"), hi = num(s, "high_52w"), chg = num(s, "change_pct");
        const pos = close !== null && lo !== null && hi !== null && hi > lo ? ((close - lo) / (hi - lo)) * 100 : null;
        const next = data.events[s.symbol]?.[0];
        return (
          <div key={s.symbol} className="panel relative overflow-hidden p-4">
            <div className="absolute inset-x-0 top-0 h-1" style={{ background: color(i) }} />
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-semibold text-white">{s.symbol}</span>
              <span className={clsx("num text-xs", (chg ?? 0) >= 0 ? "text-up" : "text-down")}>{fmtPct(chg)}</span>
            </div>
            <div className="truncate text-[11px] text-muted" title={s.name}>{s.name}</div>
            <div className="num mt-2 text-lg font-semibold text-white">{fmtPrice(close)}</div>
            <div className="text-[11px] text-muted">{s.sector ?? "Sector n/a"} · {fmtCr(s.market_cap as never)}</div>
            {pos !== null && (
              <div className="mt-3" title="Where today's price sits between the 52-week low and high">
                <div className="relative h-1.5 rounded-full bg-gradient-to-r from-white/10 to-white/25">
                  <span className="absolute -top-1 h-3.5 w-1 rounded-full bg-white" style={{ left: `calc(${pos}% - 2px)` }} />
                </div>
                <div className="num mt-1 flex justify-between text-[10px] text-muted"><span>52W {fmtPrice(lo)}</span><span>{fmtPrice(hi)}</span></div>
              </div>
            )}
            {next && <div className="mt-2 truncate text-[11px] text-slate-300" title={next.purpose}><CalendarClock className="mr-1 inline h-3 w-3 text-gold" />{day(next.date)}: {next.purpose}</div>}
          </div>
        );
      })}
    </div>
  );
}

/** Plain-language observations generated from the numbers. Facts and comparisons only. */
export function KeyDifferences({ data }: { data: Data }) {
  const notes: string[] = [];
  const st = data.stocks;
  const by = (k: keyof Stock, filter = (v: number) => true) =>
    st.map((s) => ({ s: s.symbol, v: num(s, k) })).filter((x): x is { s: string; v: number } => x.v !== null && filter(x.v)).sort((a, b) => a.v - b.v);

  const mc = by("market_cap", (v) => v > 0);
  if (mc.length >= 2 && mc[mc.length - 1].v / mc[0].v >= 1.5)
    notes.push(`${mc[mc.length - 1].s} is ${(mc[mc.length - 1].v / mc[0].v).toFixed(1)}× the size of ${mc[0].s} by market cap.`);
  const pe = by("pe", (v) => v > 0);
  if (pe.length >= 2) notes.push(`P/E ranges from ${pe[0].v.toFixed(1)}x (${pe[0].s}) to ${pe[pe.length - 1].v.toFixed(1)}x (${pe[pe.length - 1].s}): the market pays ${(pe[pe.length - 1].v / pe[0].v).toFixed(1)}× more per rupee of profit for ${pe[pe.length - 1].s}.`);
  const rg = by("revenue_growth_yoy");
  if (rg.length >= 2) notes.push(`Revenue growth over the last year: ${rg[rg.length - 1].s} ${fmtPct(rg[rg.length - 1].v)} vs ${rg[0].s} ${fmtPct(rg[0].v)}.`);
  const roe = by("roe");
  if (roe.length >= 2 && roe[roe.length - 1].v - roe[0].v >= 5) notes.push(`${roe[roe.length - 1].s} earned ${fmtPct(roe[roe.length - 1].v, false)} on shareholders' equity, ${(roe[roe.length - 1].v - roe[0].v).toFixed(1)} points more than ${roe[0].s}.`);

  const risks = st.map((s) => ({ s: s.symbol, r: data.risk[s.symbol] })).filter((x) => x.r);
  const dd = risks.filter((x) => x.r!.drawdown).sort((a, b) => a.r!.drawdown!.pct - b.r!.drawdown!.pct);
  if (dd.length) {
    const w = dd[0].r!.drawdown!;
    notes.push(`Deepest fall in the period: ${dd[0].s} ${fmtPct(w.pct)} (${mon(w.peak)} → ${mon(w.trough)}), ${w.recovered ? `back to its peak by ${mon(w.recovered)}` : "not yet back to that peak"}.`);
  }
  const vol = risks.filter((x) => x.r!.volatility !== null).sort((a, b) => a.r!.volatility! - b.r!.volatility!);
  if (vol.length >= 2) notes.push(`${vol[0].s}'s price swung the least (volatility ${vol[0].r!.volatility!.toFixed(0)}% a year); ${vol[vol.length - 1].s}'s the most (${vol[vol.length - 1].r!.volatility!.toFixed(0)}%).`);
  const corr = data.correlations.filter((c) => c.value !== null).sort((a, b) => b.value! - a.value!);
  if (corr.length) {
    const c = corr[0];
    notes.push(`${c.a} and ${c.b} moved ${c.value! >= 0.7 ? "very closely" : c.value! >= 0.4 ? "somewhat" : "largely independently"} day to day (correlation ${c.value!.toFixed(2)}).`);
  }
  const dy = by("dividend_yield", (v) => v > 0);
  if (dy.length >= 2) notes.push(`Trailing dividend yield: ${dy[dy.length - 1].s} ${fmtPct(dy[dy.length - 1].v, false)}, ${dy[0].s} ${fmtPct(dy[0].v, false)}.`);

  if (!notes.length) return null;
  return (
    <section className="panel p-5">
      <div className="mb-3 flex items-center gap-2"><Lightbulb className="h-5 w-5 text-gold" /><h2 className="text-lg font-semibold text-white">What stands out</h2></div>
      <ul className="grid gap-2 md:grid-cols-2">
        {notes.map((n) => (
          <li key={n} className="rounded-xl border border-white/[0.06] bg-black/25 px-3 py-2 text-sm leading-relaxed text-slate-300">{n}</li>
        ))}
      </ul>
      <p className="mt-3 text-[11px] text-muted">Generated from the figures below. Observations, not opinions or recommendations.</p>
    </section>
  );
}

function Bar({ value, max, color: c, negative }: { value: number; max: number; color: string; negative?: boolean }) {
  return (
    <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/[0.05]">
      <div className="h-full rounded-full" style={{ width: `${Math.min(100, (Math.abs(value) / (max || 1)) * 100)}%`, background: negative ? "#ff4d5e" : c, opacity: 0.8 }} />
    </div>
  );
}

/** Return, swing, deepest fall and sensitivity to the Nifty 50 over the selected window. */
export function RiskReturn({ data }: { data: Data }) {
  const rows = data.stocks.map((s, i) => ({ s, i, r: data.risk[s.symbol] })).filter((x) => x.r);
  if (!rows.length) return null;
  const maxRet = Math.max(...rows.map((x) => Math.abs(x.r!.total_return)));
  const maxVol = Math.max(...rows.map((x) => x.r!.volatility ?? 0));
  const maxDd = Math.max(...rows.map((x) => Math.abs(x.r!.drawdown?.pct ?? 0)));
  return (
    <section className="panel p-5">
      <div className="mb-1 flex items-center gap-2"><Activity className="h-5 w-5 text-accent" /><h2 className="text-lg font-semibold text-white">Return and risk, last {data.years} year{data.years > 1 ? "s" : ""}</h2></div>
      <p className="mb-4 text-xs text-muted">Price only, adjusted for splits and bonuses. Beta compares daily moves with the {data.benchmark.name}.</p>
      <div className={clsx("grid gap-3 md:grid-cols-2", LG_COLS[rows.length])}>
        {rows.map(({ s, i, r }) => (
          <div key={s.symbol} className="rounded-xl border border-white/[0.06] bg-black/25 p-3" style={{ borderTop: `2px solid ${color(i)}` }}>
            <div className="flex items-center justify-between"><span className="font-semibold text-white">{s.symbol}</span>
              {!r!.full_window && <span className="text-[10px] text-gold" title={`Data from ${day(r!.since)}`}>since {mon(r!.since)}</span>}</div>
            <dl className="mt-2 space-y-2 text-xs">
              <div><div className="flex justify-between"><dt className="text-muted">Return{r!.cagr !== null && " (p.a.)"}</dt>
                <dd className={clsx("num", r!.total_return >= 0 ? "text-up" : "text-down")}>{fmtPct(r!.total_return)}{r!.cagr !== null && <span className="text-muted"> ({fmtPct(r!.cagr)})</span>}</dd></div>
                <Bar value={r!.total_return} max={maxRet} color="#00d47e" negative={r!.total_return < 0} /></div>
              <div><div className="flex justify-between"><dt className="text-muted" title="Annualised standard deviation of daily returns">Volatility</dt><dd className="num text-white">{r!.volatility !== null ? `${r!.volatility.toFixed(1)}%` : "—"}</dd></div>
                <Bar value={r!.volatility ?? 0} max={maxVol} color="#f472b6" /></div>
              <div><div className="flex justify-between"><dt className="text-muted" title="Largest fall from a high to a later low">Deepest fall</dt><dd className="num text-down">{r!.drawdown ? fmtPct(r!.drawdown.pct) : "—"}</dd></div>
                <Bar value={r!.drawdown?.pct ?? 0} max={maxDd} color="#ff4d5e" negative />
                {r!.drawdown && <div className="mt-0.5 text-[10px] text-muted">{mon(r!.drawdown.peak)} → {mon(r!.drawdown.trough)} · {r!.drawdown.recovered ? `recovered ${mon(r!.drawdown.recovered)}` : `now ${fmtPct(r!.drawdown.current_pct)} from high`}</div>}</div>
              <div className="flex justify-between"><dt className="text-muted" title="1.0 = moved in line with the index on average; above 1 = larger swings">Beta</dt><dd className="num text-white">{r!.beta?.toFixed(2) ?? "—"}</dd></div>
              <div className="flex justify-between"><dt className="text-muted">Up days</dt><dd className="num text-white">{r!.up_days_pct !== null ? `${r!.up_days_pct}%` : "—"}</dd></div>
              <div className="flex justify-between"><dt className="text-muted">Best / worst day</dt>
                <dd className="num"><span className="text-up" title={r!.best_day ? day(r!.best_day.date) : ""}>{fmtPct(r!.best_day?.pct)}</span> / <span className="text-down" title={r!.worst_day ? day(r!.worst_day.date) : ""}>{fmtPct(r!.worst_day?.pct)}</span></dd></div>
            </dl>
          </div>
        ))}
      </div>
    </section>
  );
}

/** How closely each pair's daily moves were linked. */
export function Correlations({ data }: { data: Data }) {
  const syms = data.stocks.map((s) => s.symbol);
  const get = (a: string, b: string) => data.correlations.find((c) => (c.a === a && c.b === b) || (c.a === b && c.b === a))?.value ?? null;
  if (!data.correlations.some((c) => c.value !== null)) return null;
  const cell = (v: number | null) => (v === null ? "transparent" : `rgba(124,156,255,${0.08 + Math.max(0, v) * 0.6})`);
  return (
    <section className="panel p-5">
      <div className="mb-1 flex items-center gap-2"><Waves className="h-5 w-5 text-cyan-400" /><h2 className="text-lg font-semibold text-white">Do they move together?</h2></div>
      <p className="mb-4 text-xs text-muted">Correlation of daily price changes, last {data.years}Y. 1 = always moved together, 0 = unrelated, below 0 = tended to move opposite.</p>
      <div className="overflow-x-auto">
        <table className="mx-auto text-xs">
          <thead><tr><th />{syms.map((s, i) => <th key={s} className="px-2 pb-2 font-medium" style={{ color: color(i) }}>{s}</th>)}</tr></thead>
          <tbody>
            {syms.map((a, i) => (
              <tr key={a}>
                <th className="pr-3 text-right font-medium" style={{ color: color(i) }}>{a}</th>
                {syms.map((b, j) => {
                  const v = i === j ? 1 : get(a, b);
                  return <td key={b} className="p-0.5"><div className="num flex h-11 w-16 items-center justify-center rounded-md text-white" style={{ background: i === j ? "rgba(255,255,255,0.04)" : cell(v) }}>{i === j ? "—" : v?.toFixed(2) ?? "n/a"}</div></td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/** Last eight quarters of revenue and net profit, side by side on one scale per stock. */
export function QuarterlyTrend({ data }: { data: Data }) {
  const stocks = data.stocks.map((s, i) => ({ s, i, q: data.quarters[s.symbol] ?? [] })).filter((x) => x.q.length >= 2);
  if (!stocks.length) return null;
  return (
    <section className="panel p-5">
      <div className="mb-1 flex items-center gap-2"><GitCompareArrows className="h-5 w-5 text-violet-400" /><h2 className="text-lg font-semibold text-white">Quarterly revenue and profit</h2></div>
      <p className="mb-4 text-xs text-muted">From results filed with NSE, ₹ crore. Bars: revenue; dots: net profit (each stock on its own scale).</p>
      <div className="grid gap-4 sm:grid-cols-2">
        {stocks.map(({ s, i, q }) => {
          const maxRev = Math.max(1, ...q.map((x) => toNum(x.revenue as never) ?? 0));
          const profits = q.map((x) => toNum(x.net_profit as never));
          const maxP = Math.max(1, ...profits.map((p) => Math.abs(p ?? 0)));
          const last = q[q.length - 1], yearAgo = q.length >= 5 ? q[q.length - 5] : null;
          const yoy = (a: number | null, b: number | null) => (a !== null && b !== null && b > 0 ? ((a - b) / b) * 100 : null);
          const revYoy = yearAgo && yoy(toNum(last.revenue as never), toNum(yearAgo.revenue as never));
          const patYoy = yearAgo && yoy(toNum(last.net_profit as never), toNum(yearAgo.net_profit as never));
          return (
            <div key={s.symbol} className="rounded-xl border border-white/[0.06] bg-black/25 p-3">
              <div className="flex items-baseline justify-between text-sm"><span className="font-semibold" style={{ color: color(i) }}>{s.symbol}</span>
                <span className="text-[11px] text-muted">latest vs year-ago quarter</span></div>
              <div className="num mb-2 flex gap-3 text-[11px]">
                <span className="text-muted">Revenue <span className={clsx((revYoy ?? 0) >= 0 ? "text-up" : "text-down")}>{revYoy != null ? fmtPct(revYoy) : "—"}</span></span>
                <span className="text-muted">Profit <span className={clsx((patYoy ?? 0) >= 0 ? "text-up" : "text-down")}>{patYoy != null ? fmtPct(patYoy) : "—"}</span></span>
              </div>
              <div className="relative flex h-24 items-end gap-1">
                {q.map((x, k) => {
                  const rev = toNum(x.revenue as never) ?? 0, p = profits[k];
                  return (
                    <div key={x.period_end} className="relative flex h-full flex-1 flex-col justify-end" title={`${mon(x.period_end)}: revenue ₹${Math.round(rev).toLocaleString("en-IN")} Cr, profit ₹${p !== null ? Math.round(p).toLocaleString("en-IN") : "—"} Cr`}>
                      <div className="rounded-t" style={{ height: `${(rev / maxRev) * 100}%`, background: `${color(i)}55` }} />
                      {p !== null && <span className={clsx("absolute left-1/2 h-2 w-2 -translate-x-1/2 rounded-full ring-2 ring-bg", p >= 0 ? "bg-white" : "bg-down")} style={{ bottom: `calc(${(Math.max(0, p) / maxP) * 90}% - 4px)` }} />}
                    </div>
                  );
                })}
              </div>
              <div className="mt-1 flex justify-between text-[10px] text-muted"><span>{mon(q[0].period_end)}</span><span>{mon(last.period_end)}</span></div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
