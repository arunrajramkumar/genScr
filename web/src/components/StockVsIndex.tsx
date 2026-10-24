"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { Scale } from "lucide-react";
import { LINE_COLORS } from "@/components/chartColors";
import { SectionNote } from "@/components/Legal";
import { Loading, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { changeClass, fmtNum, fmtPct } from "@/lib/format";
import { useInView } from "@/lib/useInView";

const CompareChart = dynamic(() => import("@/components/PriceChart").then((m) => m.CompareChart), { ssr: false, loading: () => <Loading /> });
const LineChart = dynamic(() => import("@/components/PriceChart").then((m) => m.SimpleLineChart), { ssr: false, loading: () => <Loading /> });

interface VsIndex {
  start: string;
  end: string;
  available_years: number;
  series: { time: string; stock: number; index: number; relative: number }[];
  returns: { period: string; annualised: boolean; stock: number; index: number; difference: number }[];
  stats: {
    beta: number | null; correlation: number | null; volatility_stock: number; volatility_index: number;
    max_drawdown_stock: number; max_drawdown_index: number; up_capture: number | null; down_capture: number | null;
    months: number; months_ahead: number;
  } | null;
  calendar: { year: number; stock: number; index: number; partial: boolean }[];
  index: { name: string; slug: string; pe: number | null; pb: number | null; div_yield: number | null } | null;
}

const BROAD = ["Nifty 50", "Nifty Next 50", "Nifty 500", "Nifty Midcap 150", "Nifty Smallcap 250", "Nifty Microcap 250"];
const slug = (name: string) => name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

/** A stock against any NSE index: growth, relative strength, returns, risk and calendar years, all historical. */
export default function StockVsIndex({ symbol, memberOf = [], pe }: { symbol: string; memberOf?: string[]; pe?: number | null }) {
  const { ref, inView } = useInView<HTMLElement>();
  const choices = useMemo(() => [...new Set([...BROAD, ...memberOf])], [memberOf]);
  const [index, setIndex] = useState("nifty-50");
  const [years, setYears] = useState(5);
  const [view, setView] = useState<"growth" | "relative">("growth");
  const [d, setD] = useState<VsIndex | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!inView) return;
    setError(null);
    api<VsIndex>(`/stocks/${encodeURIComponent(symbol)}/vs-index?index=${index}&years=${years}`)
      .then(setD)
      .catch((e) => setError(e.message));
  }, [inView, symbol, index, years]);

  const name = d?.index?.name ?? choices.find((c) => slug(c) === index) ?? index;
  const series = useMemo(() => d && {
    [symbol]: d.series.map((p) => ({ time: p.time, value: p.stock })),
    [name]: d.series.map((p) => ({ time: p.time, value: p.index })),
  }, [d, symbol, name]);
  const relative = useMemo(() => d?.series.map((p) => ({ time: p.time, value: p.relative })) ?? [], [d]);

  const last = d?.series[d.series.length - 1];
  const shownYears = d ? Math.min(years, d.available_years) : years;
  const st = d?.stats;

  return (
    <section ref={ref} className="panel p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
          <Scale className="h-5 w-5 text-accent" /> {symbol} vs
          <select value={index} onChange={(e) => setIndex(e.target.value)} aria-label="Index to compare with"
            className="rounded-lg border border-line bg-panel px-2 py-1 text-base font-semibold text-white outline-none focus:border-accent/70">
            {choices.map((c) => <option key={c} value={slug(c)}>{c}{memberOf.includes(c) ? " ✓" : ""}</option>)}
          </select>
        </h2>
        <div className="seg">
          {[1, 3, 5, 10].map((y) => <button key={y} onClick={() => setYears(y)} aria-pressed={years === y} className={clsx("seg-btn", years === y && "seg-btn-active")}>{y}Y</button>)}
        </div>
      </div>
      {memberOf.length > 0 && <p className="mt-1 text-xs text-muted">✓ = indices {symbol} is part of.</p>}

      {error && <p className="mt-4 text-sm text-muted">No comparison available: {error}</p>}
      {!d && !error && <div className="mt-4"><Loading /></div>}

      {d && last && (
        <>
          <p className="mt-3 text-sm text-slate-300">
            ₹100 in {symbol} on {new Date(d.start).toLocaleDateString("en-IN", { dateStyle: "medium" })} would be{" "}
            <span className={clsx("num font-semibold", changeClass(last.stock - 100))}>₹{fmtNum(last.stock, 0)}</span>; in the {name}, {" "}
            <span className={clsx("num font-semibold", changeClass(last.index - 100))}>₹{fmtNum(last.index, 0)}</span>
            {shownYears < years && <> (only {shownYears.toFixed(1)} years of shared history)</>}.
            {st && <> {symbol} finished ahead of the index in <span className="num text-white">{st.months_ahead}</span> of <span className="num text-white">{st.months}</span> months.</>}
          </p>

          <div className="mt-4 flex items-center justify-between gap-3">
            <div className="seg">
              <button onClick={() => setView("growth")} aria-pressed={view === "growth"} className={clsx("seg-btn", view === "growth" && "seg-btn-active")}>Growth of ₹100</button>
              <button onClick={() => setView("relative")} aria-pressed={view === "relative"} className={clsx("seg-btn", view === "relative" && "seg-btn-active")}>Relative strength</button>
            </div>
            {view === "growth" && (
              <div className="flex gap-3 text-xs">
                <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: LINE_COLORS[0] }} />{symbol}</span>
                <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: LINE_COLORS[1] }} />{name}</span>
              </div>
            )}
          </div>
          <div className="mt-2">
            {view === "growth" && series ? <CompareChart series={series} /> : <LineChart series={relative} positive={(last.relative ?? 100) >= 100} median={100} refLabel="level" />}
          </div>
          {view === "relative" && (
            <p className="mt-1 text-xs text-muted">The stock divided by the index, starting at 100. Rising means the stock moved more than the index over that stretch; falling means less.</p>
          )}

          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-muted">
                    <th scope="col" className="py-2 font-medium">Period</th>
                    <th scope="col" className="py-2 text-right font-medium">{symbol}</th>
                    <th scope="col" className="py-2 text-right font-medium">{name}</th>
                    <th scope="col" className="py-2 text-right font-medium">Difference</th>
                  </tr>
                </thead>
                <tbody>
                  {d.returns.map((r) => (
                    <tr key={r.period} className="table-row">
                      <th scope="row" className="py-2 text-left font-normal text-slate-300">{r.period}{r.annualised && <span className="text-xs text-muted"> p.a.</span>}</th>
                      <td className={clsx("num py-2 text-right", changeClass(r.stock))}>{fmtPct(r.stock)}</td>
                      <td className={clsx("num py-2 text-right", changeClass(r.index))}>{fmtPct(r.index)}</td>
                      <td className="num py-2 text-right text-slate-200">{r.difference > 0 ? "+" : ""}{fmtNum(r.difference)} pts</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-muted">
                    <th scope="col" className="py-2 font-medium">Calendar year</th>
                    <th scope="col" className="py-2 text-right font-medium">{symbol}</th>
                    <th scope="col" className="py-2 text-right font-medium">{name}</th>
                  </tr>
                </thead>
                <tbody>
                  {[...d.calendar].reverse().map((c) => (
                    <tr key={c.year} className="table-row">
                      <th scope="row" className="py-2 text-left font-normal text-slate-300">{c.year}{c.partial && <span className="text-xs text-muted"> (part)</span>}</th>
                      <td className={clsx("num py-2 text-right", changeClass(c.stock))}>{fmtPct(c.stock)}</td>
                      <td className={clsx("num py-2 text-right", changeClass(c.index))}>{fmtPct(c.index)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {st && (
            <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
              <Stat label="Beta" value={fmtNum(st.beta)} sub="Average weekly move per 1% index move" />
              <Stat label="Correlation" value={fmtNum(st.correlation)} sub="1 = always moved together, 0 = unrelated" />
              <Stat label="Volatility" value={<span className="num">{fmtNum(st.volatility_stock, 1)}%</span>} sub={`Index ${fmtNum(st.volatility_index, 1)}% (annualised)`} />
              <Stat label="Worst fall" value={<span className="text-down">{fmtPct(st.max_drawdown_stock)}</span>} sub={`Index ${fmtPct(st.max_drawdown_index)}`} />
              <Stat label="Up-month capture" value={st.up_capture !== null ? `${fmtNum(st.up_capture, 0)}%` : "—"} sub="Stock's average move as % of the index's, in months the index rose" />
              <Stat label="Down-month capture" value={st.down_capture !== null ? `${fmtNum(st.down_capture, 0)}%` : "—"} sub="Same, in months the index fell" />
              <Stat label="Months ahead" value={`${st.months_ahead} / ${st.months}`} sub="Months the stock moved more than the index" />
              <Stat label="P/E" value={<span className="num">{fmtNum(pe, 1)}</span>} sub={`${name} ${fmtNum(d.index?.pe, 1)} (NSE)`} />
            </div>
          )}
          <SectionNote>
            Computed by genScr from NSE closing prices over common trading days. Both sides are price-only: the stock is adjusted for
            splits and bonuses, the index is NSE&apos;s price index, and dividends are excluded from both. Historical comparison only; past
            behaviour does not indicate future returns and this is not a recommendation.
          </SectionNote>
        </>
      )}
    </section>
  );
}
