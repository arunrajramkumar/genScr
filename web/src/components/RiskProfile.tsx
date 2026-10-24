"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { Activity, CalendarRange } from "lucide-react";
import { SectionNote } from "./Legal";
import { Loading } from "./ui";
import { api } from "@/lib/api";
import { useInView } from "@/lib/useInView";
import type { RiskResponse } from "@/lib/types";

const UnderwaterChart = dynamic(() => import("./PriceChart").then((m) => m.UnderwaterChart), { ssr: false, loading: () => <Loading /> });

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const mon = (d: string) => new Date(d).toLocaleDateString("en-IN", { month: "short", year: "numeric" });
const pct = (v: number | null | undefined, sign = true) => (v === null || v === undefined ? "—" : `${sign && v > 0 ? "+" : ""}${v.toFixed(1)}%`);

function heat(v: number | undefined) {
  if (v === undefined) return "bg-white/[0.03] text-transparent";
  if (v >= 8) return "bg-up/70 text-white";
  if (v >= 3) return "bg-up/45 text-white";
  if (v > 0) return "bg-up/20 text-slate-200";
  if (v <= -8) return "bg-down/70 text-white";
  if (v <= -3) return "bg-down/45 text-white";
  if (v < 0) return "bg-down/20 text-slate-200";
  return "bg-white/10 text-slate-300";
}

export default function RiskProfile({ symbol }: { symbol: string }) {
  const { ref, inView } = useInView<HTMLElement>();
  const [d, setD] = useState<RiskResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!inView) return;
    api<RiskResponse>(`/stocks/${encodeURIComponent(symbol)}/risk`).then(setD).catch(() => setFailed(true));
  }, [inView, symbol]);

  const grid = useMemo(() => {
    const m = new Map<string, number>();
    d?.monthly.forEach((x) => m.set(`${x.year}-${x.month}`, x.return_pct));
    const years = Array.from(new Set(d?.monthly.map((x) => x.year) ?? [])).sort((a, b) => b - a);
    return { m, years };
  }, [d]);

  const worst = d?.worst_drawdowns[0];
  const best = d?.seasonality.length ? [...d.seasonality].sort((a, b) => b.up / b.years - a.up / a.years || b.avg_pct - a.avg_pct)[0] : null;

  return (
    <section ref={ref} className="panel p-5">
      <div className="flex items-center gap-2">
        <Activity className="h-5 w-5 text-down" />
        <h2 className="text-lg font-semibold text-white">Risk, drawdowns &amp; seasonality</h2>
      </div>

      {!d && !failed && inView && <Loading />}
      {failed && <p className="mt-3 text-sm text-muted">Not enough price history yet.</p>}

      {d && (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Tile label="Worst fall" value={pct(worst?.depth_pct)} tone="down"
              sub={worst ? `${mon(worst.peak_date)} → ${mon(worst.trough_date)}` : undefined} />
            <Tile label="Recovery" value={worst ? (worst.days_to_recover !== null ? `${Math.round(worst.days_to_recover / 30)} months` : "Not yet") : "—"}
              sub={worst?.recovered_date ? `back to peak ${mon(worst.recovered_date)}` : worst ? `${Math.round(worst.days_underwater / 30)} months below peak` : undefined} />
            <Tile label="Now vs peak" value={pct(d.current_drawdown_pct)} tone={d.current_drawdown_pct > -5 ? "up" : "down"} sub={`peak ${mon(d.peak_date)}`} />
            <Tile label="Volatility (1Y)" value={pct(d.volatility_1y_pct, false)} sub={d.up_days_1y_pct !== null ? `${d.up_days_1y_pct.toFixed(0)}% of days closed up` : undefined} />
          </div>

          <div className="mt-5">
            <div className="label mb-1">Distance below previous peak</div>
            <UnderwaterChart series={d.underwater} />
          </div>

          {d.calendar_years.length > 0 && (
            <div className="mt-5">
              <div className="label mb-2">Calendar-year returns</div>
              <div className="flex flex-wrap gap-1.5">
                {d.calendar_years.map((y) => (
                  <div key={y.year} className={clsx("min-w-[64px] rounded-lg px-2 py-1.5 text-center", y.return_pct >= 0 ? "bg-up/15" : "bg-down/15")}>
                    <div className="num text-[10px] text-muted">{y.year}{y.partial ? " YTD" : ""}</div>
                    <div className={clsx("num text-sm font-semibold", y.return_pct >= 0 ? "text-up" : "text-down")}>{pct(y.return_pct)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {grid.years.length > 1 && (
            <div className="mt-5">
              <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
                <span className="label flex items-center gap-1.5"><CalendarRange className="h-3.5 w-3.5" /> Monthly returns heatmap</span>
                {best && <span className="text-xs text-muted">Most consistent month: <span className="text-white">{MONTHS[best.month - 1]}</span>, up in {best.up} of {best.years} years</span>}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] border-separate border-spacing-0.5 text-[10px]">
                  <thead>
                    <tr>
                      <th />
                      {MONTHS.map((m) => <th key={m} className="font-normal text-muted">{m}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {grid.years.map((y) => (
                      <tr key={y}>
                        <td className="num pr-1 text-right text-muted">{y}</td>
                        {MONTHS.map((_, i) => {
                          const v = grid.m.get(`${y}-${i + 1}`);
                          return (
                            <td key={i} className={clsx("num rounded py-1 text-center", heat(v))} title={v !== undefined ? `${MONTHS[i]} ${y}: ${pct(v)}` : undefined}>
                              {v !== undefined ? v.toFixed(0) : "·"}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                    <tr>
                      <td className="pr-1 text-right text-muted">Up</td>
                      {MONTHS.map((_, i) => {
                        const s = d.seasonality.find((x) => x.month === i + 1);
                        return <td key={i} className="num py-1 text-center text-slate-300">{s ? `${s.up}/${s.years}` : ""}</td>;
                      })}
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}
          <div className="mt-3">
            <SectionNote>Computed from split/bonus-adjusted closing prices since {mon(d.since)} (price only, excluding dividends). Historical patterns describe the past and do not indicate future returns.</SectionNote>
          </div>
        </>
      )}
    </section>
  );
}

function Tile({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "up" | "down" }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-black/25 p-3">
      <div className="label">{label}</div>
      <div className={clsx("num mt-1 text-lg font-semibold", tone === "down" ? "text-down" : tone === "up" ? "text-up" : "text-white")}>{value}</div>
      {sub && <div className="text-[11px] text-muted">{sub}</div>}
    </div>
  );
}
