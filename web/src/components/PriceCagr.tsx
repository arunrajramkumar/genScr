"use client";

import { useMemo } from "react";
import clsx from "clsx";
import { TrendingUp } from "lucide-react";
import { availableYears, lumpsum } from "@/lib/returns";
import type { Candle } from "@/lib/types";

const YEARS = [1, 2, 3, 4, 5];

/** Annualised price growth over the last 1-5 years (split/bonus-adjusted, excluding dividends). */
export default function PriceCagr({ prices }: { prices: Candle[] }) {
  const rows = useMemo(() => {
    const max = availableYears(prices);
    return YEARS.map((y) => {
      const r = y <= max ? lumpsum(prices, y, 1) : null;
      return { y, cagr: r?.cagr ?? null, total: r ? r.gainPct : null };
    });
  }, [prices]);

  const scale = Math.max(10, ...rows.map((r) => Math.abs(r.cagr ?? 0)));

  return (
    <section className="panel p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-accent" />
          <h2 className="text-lg font-semibold text-white">Price growth (CAGR)</h2>
        </div>
        <span className="text-[11px] text-muted">Annualised, split/bonus-adjusted, excluding dividends</span>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {rows.map(({ y, cagr, total }) => {
          const up = (cagr ?? 0) >= 0;
          return (
            <div key={y} className="rounded-xl border border-white/[0.06] bg-black/25 p-3">
              <div className="label">{y} year{y > 1 ? "s" : ""}</div>
              <div className={clsx("num mt-1 text-2xl font-bold", cagr === null ? "text-muted" : up ? "text-up" : "text-down")}>
                {cagr === null ? "—" : `${cagr > 0 ? "+" : ""}${cagr.toFixed(1)}%`}
              </div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/5">
                {cagr !== null && (
                  <div className={clsx("h-full rounded-full", up ? "bg-up/70" : "bg-down/70")} style={{ width: `${(Math.abs(cagr) / scale) * 100}%` }} />
                )}
              </div>
              <div className="num mt-1.5 text-[11px] text-muted">
                {total === null ? "Not enough history" : `${total > 0 ? "+" : ""}${total.toFixed(0)}% total`}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
