"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { Coins } from "lucide-react";
import { SectionNote } from "./Legal";
import { Loading } from "./ui";
import { api } from "@/lib/api";
import { useInView } from "@/lib/useInView";
import type { DividendHistoryResponse } from "@/lib/types";

const day = (d: string) => new Date(d).toLocaleDateString("en-IN", { dateStyle: "medium" });
const now = new Date();
const CURRENT_FY = now.getMonth() >= 3 ? now.getFullYear() + 1 : now.getFullYear(); // FY ends in March

export default function DividendHistory({ symbol }: { symbol: string }) {
  const { ref, inView } = useInView<HTMLElement>();
  const [data, setData] = useState<DividendHistoryResponse | null>(null);
  const [basis, setBasis] = useState<"adjusted" | "declared">("adjusted");
  const [showAll, setShowAll] = useState(false);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    if (!inView) return;
    api<DividendHistoryResponse>(`/stocks/${encodeURIComponent(symbol)}/dividends`).then(setData).catch(() => setData(null));
  }, [inView, symbol]);

  const years = data?.years ?? [];
  const max = Math.max(0.0001, ...years.map((y) => y[basis]));
  const s = data?.stats;
  const shown = hover !== null ? years[hover] : years[years.length - 1];

  return (
    <section ref={ref} className="panel p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Coins className="h-5 w-5 text-gold" />
          <h2 className="text-lg font-semibold text-white">Dividend history</h2>
        </div>
        {years.length > 0 && (
          <div className="seg">
            <button onClick={() => setBasis("adjusted")} className={clsx("seg-btn", basis === "adjusted" && "seg-btn-active")} title="Restated for later bonuses and splits, so years are comparable">In today&apos;s shares</button>
            <button onClick={() => setBasis("declared")} className={clsx("seg-btn", basis === "declared" && "seg-btn-active")}>As declared</button>
          </div>
        )}
      </div>

      {!data && inView && <Loading />}
      {data && years.length === 0 && <p className="mt-3 text-sm text-muted">No dividends on record since 2005.</p>}

      {data && s && years.length > 0 && (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Tile label="Paid every year for" value={`${s.paying_streak_years} yr${s.paying_streak_years === 1 ? "" : "s"}`} />
            <Tile label="Raised dividend for" value={`${s.growth_streak_years} yr${s.growth_streak_years === 1 ? "" : "s"} in a row`} />
            <Tile label="5-year dividend CAGR" value={s.dps_cagr_5y === null ? "—" : `${s.dps_cagr_5y > 0 ? "+" : ""}${s.dps_cagr_5y.toFixed(1)}%`} />
            <Tile label="Payments since 2005" value={`${s.total_payments}`} sub={s.first_dividend ? `first ${day(s.first_dividend)}` : undefined} />
          </div>

          <div className="mt-5">
            <div className="mb-2 flex items-baseline justify-between text-xs text-muted">
              <span>Per-share dividend by financial year</span>
              {shown && (
                <span className="num text-slate-300">
                  FY{String(shown.fy).slice(2)}{shown.fy === CURRENT_FY ? " so far" : ""}: ₹{shown[basis].toFixed(2)} · {shown.payments} payment{shown.payments > 1 ? "s" : ""}
                  {shown.yield_pct !== null && ` · ${shown.yield_pct.toFixed(2)}% yield`}
                </span>
              )}
            </div>
            <div className="flex h-40 items-end gap-1" onMouseLeave={() => setHover(null)}>
              {years.map((y, i) => (
                <div key={y.fy} className="group flex h-full flex-1 flex-col items-center justify-end" onMouseEnter={() => setHover(i)}>
                  <div
                    className={clsx(
                      "w-full rounded-t transition-all duration-500",
                      y.fy === CURRENT_FY
                        ? "border border-dashed border-gold bg-[repeating-linear-gradient(45deg,rgba(245,185,66,0.35)_0_4px,transparent_4px_8px)]"
                        : i === years.length - 1 ? "bg-gold" : "bg-gold/45 group-hover:bg-gold/80",
                    )}
                    title={y.fy === CURRENT_FY ? "Current financial year (in progress)" : undefined}
                    style={{ height: `${Math.max(2, (y[basis] / max) * 100)}%` }}
                  />
                </div>
              ))}
            </div>
            <div className="mt-1 flex gap-1 text-[9px] text-muted">
              {years.map((y, i) => (
                <span key={y.fy} className="num flex-1 text-center">{i % Math.ceil(years.length / 10) === 0 || i === years.length - 1 ? `FY${String(y.fy).slice(2)}` : ""}</span>
              ))}
            </div>
          </div>

          <div className="mt-4">
            <button onClick={() => setShowAll((v) => !v)} className="text-xs text-accent hover:underline">
              {showAll ? "Hide" : "Show"} all {data.payments.length} payments
            </button>
            {showAll && (
              <div className="mt-2 max-h-72 overflow-auto rounded-xl border border-line">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-panel text-left text-muted">
                    <tr><th className="px-3 py-2">Ex-date</th><th className="px-3 py-2 text-right">Declared</th><th className="px-3 py-2 text-right">In today&apos;s shares</th><th className="px-3 py-2 text-right">Yield then</th><th className="px-3 py-2">As announced</th></tr>
                  </thead>
                  <tbody>
                    {[...data.payments].reverse().map((p) => (
                      <tr key={p.ex_date + p.amount} className="table-row">
                        <td className="num px-3 py-1.5">{day(p.ex_date)}</td>
                        <td className="num px-3 py-1.5 text-right">₹{p.amount}</td>
                        <td className="num px-3 py-1.5 text-right">₹{p.adjusted_amount}</td>
                        <td className="num px-3 py-1.5 text-right">{p.yield_pct === null ? "—" : `${p.yield_pct}%`}</td>
                        <td className="max-w-[260px] truncate px-3 py-1.5 text-muted" title={p.subject ?? ""}>{p.subject}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          <div className="mt-3">
            <SectionNote>Source: NSE corporate actions (records from 2005; the oldest records can be incomplete, e.g. a missing split makes early "today's shares" amounts too high). Yield uses the closing price on the ex-date. Past dividends do not indicate future dividends.</SectionNote>
          </div>
        </>
      )}
    </section>
  );
}

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-black/25 p-3">
      <div className="label">{label}</div>
      <div className="num mt-1 text-lg font-semibold text-white">{value}</div>
      {sub && <div className="text-[11px] text-muted">{sub}</div>}
    </div>
  );
}
