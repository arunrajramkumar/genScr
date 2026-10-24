"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { Medal } from "lucide-react";
import { SectionNote } from "./Legal";
import { Loading } from "./ui";
import { api } from "@/lib/api";
import { fmtField } from "@/lib/format";
import { useInView } from "@/lib/useInView";
import type { RanksResponse } from "@/lib/types";

const UNITS: Record<string, string> = {
  roe: "%", roce: "%", net_margin: "%", revenue_growth_yoy: "%", profit_growth_yoy: "%", pe: "x", pb: "x",
  debt_to_equity: "x", dividend_yield: "%", return_1y: "%", piotroski_f: "/9", market_cap: "₹ Cr",
};

function tone(p: number) {
  if (p >= 75) return { bar: "bg-up", text: "text-up" };
  if (p >= 40) return { bar: "bg-gold", text: "text-gold" };
  return { bar: "bg-down/80", text: "text-down" };
}

export default function PeerRanks({ symbol }: { symbol: string }) {
  const { ref, inView } = useInView<HTMLElement>();
  const [data, setData] = useState<RanksResponse | null>(null);
  const [scope, setScope] = useState<"sector" | "market">("sector");

  useEffect(() => {
    if (!inView) return;
    api<RanksResponse>(`/stocks/${encodeURIComponent(symbol)}/ranks`).then((d) => {
      setData(d);
      if (!d.metrics.some((m) => m.sector_percentile !== undefined)) setScope("market");
    }).catch(() => setData(null));
  }, [inView, symbol]);

  const hasSector = !!data?.metrics.some((m) => m.sector_percentile !== undefined);
  const metrics = (data?.metrics ?? []).filter((m) => scope === "market" || m.sector_percentile !== undefined);

  return (
    <section ref={ref} className="panel p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Medal className="h-5 w-5 text-gold" />
          <h2 className="text-lg font-semibold text-white">Where {symbol} stands</h2>
        </div>
        {data && (
          <div className="seg">
            {hasSector && (
              <button onClick={() => setScope("sector")} className={clsx("seg-btn", scope === "sector" && "seg-btn-active")}>
                vs {data.sector} ({data.sector_size})
              </button>
            )}
            <button onClick={() => setScope("market")} className={clsx("seg-btn", scope === "market" && "seg-btn-active")}>vs all NSE stocks</button>
          </div>
        )}
      </div>

      {!data && inView && <Loading />}
      {data && metrics.length === 0 && <p className="mt-3 text-sm text-muted">Not enough data to compare yet.</p>}

      {metrics.length > 0 && (
        <div className="mt-4 grid gap-x-8 gap-y-3 md:grid-cols-2">
          {metrics.map((m) => {
            const p = scope === "sector" ? m.sector_percentile! : m.market_percentile;
            const rank = scope === "sector" ? m.sector_rank! : m.market_rank;
            const total = scope === "sector" ? m.sector_total! : m.market_total;
            const t = tone(p);
            return (
              <div key={m.field}>
                <div className="flex items-baseline justify-between gap-2 text-sm">
                  <span className="text-slate-300">{m.label}</span>
                  <span className="num text-white">{fmtField(m.value, UNITS[m.field] ?? "", m.field)}</span>
                </div>
                <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-white/5">
                  <div className={clsx("h-full rounded-full transition-all duration-700", t.bar)} style={{ width: `${Math.max(3, p)}%` }} />
                </div>
                <div className="mt-1 flex justify-between text-[11px] text-muted">
                  <span>Ahead of <span className={clsx("num font-medium", t.text)}>{p.toFixed(0)}%</span></span>
                  <span className="num">#{rank} of {total}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
      <div className="mt-4">
        <SectionNote>Percentile among companies with data, as of the latest close. A higher bar means ahead of more companies on that metric (for P/E, P/B and debt, lower values rank first). Descriptive only, not a rating.</SectionNote>
      </div>
    </section>
  );
}
