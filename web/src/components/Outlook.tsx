"use client";

import { useMemo } from "react";
import clsx from "clsx";
import { Info, TrendingDown, TrendingUp, Minus } from "lucide-react";
import { outlook } from "@/lib/returns";
import { toNum } from "@/lib/format";
import type { Candle, Fundamental } from "@/lib/types";

const inr = (v: number) => `₹${Math.round(v).toLocaleString("en-IN")}`;

const STYLE = {
  Bear: { icon: TrendingDown, ring: "border-down/25", text: "text-down", bg: "bg-down/[0.06]" },
  Base: { icon: Minus, ring: "border-accent/30", text: "text-accent", bg: "bg-accent/[0.06]" },
  Bull: { icon: TrendingUp, ring: "border-up/25", text: "text-up", bg: "bg-up/[0.06]" },
} as const;

export default function Outlook({ prices, funds }: { prices: Candle[]; funds: Fundamental[] }) {
  const o = useMemo(
    () => outlook(prices, funds.map((f) => ({ period_end: f.period_end, net_profit: toNum(f.net_profit) }))),
    [prices, funds],
  );

  return (
    <section className="panel p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-gold" />
          <h2 className="text-lg font-semibold text-white">5-year outlook</h2>
          <span className="rounded-full border border-gold/30 bg-gold/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-gold">Scenarios, not a forecast</span>
        </div>
        {o && (
          <span className="text-xs text-muted">
            Data confidence:{" "}
            <span className={clsx("font-medium", o.confidence === "high" ? "text-up" : o.confidence === "medium" ? "text-gold" : "text-down")}>{o.confidence}</span>
          </span>
        )}
      </div>

      {!o ? (
        <p className="mt-3 text-sm text-muted">Not enough price history or financials to build scenarios yet.</p>
      ) : (
        <>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            {o.scenarios.map((s) => {
              const st = STYLE[s.name];
              const Icon = st.icon;
              return (
                <div key={s.name} className={clsx("rounded-2xl border p-4", st.ring, st.bg)}>
                  <div className={clsx("flex items-center gap-1.5 text-sm font-semibold", st.text)}>
                    <Icon className="h-4 w-4" /> {s.name} case
                  </div>
                  <div className={clsx("num mt-2 text-3xl font-bold", st.text)}>
                    {s.cagr > 0 ? "+" : ""}{s.cagr.toFixed(1)}%<span className="text-sm font-normal text-muted"> /yr</span>
                  </div>
                  <div className="mt-2 text-xs text-muted">
                    ₹10,000 → <span className="num font-semibold text-white">{inr(s.value)}</span> in 5 yrs
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-4 grid gap-2 text-xs text-muted sm:grid-cols-3">
            <Input label={`Price CAGR (${o.priceYears}Y)`} value={o.priceCagr} />
            <Input label={o.profitYears ? `Net profit CAGR (${o.profitYears}Y)` : "Net profit CAGR"} value={o.profitCagr} />
            <Input label="Annual volatility" value={o.vol} unsigned />
          </div>

          <details className="mt-3 text-xs text-muted">
            <summary className="flex cursor-pointer items-center gap-1 hover:text-white"><Info className="h-3.5 w-3.5" /> How this is calculated</summary>
            <p className="mt-2 leading-relaxed">
              <b className="text-slate-300">Base</b> averages the stock&apos;s historical price CAGR and its net-profit CAGR (which assumes the P/E multiple stays the same).{" "}
              <b className="text-slate-300">Bear/Bull</b> are base ∓ annual volatility ÷ √5, roughly a one-standard-deviation range for a 5-year annualised return.
              These are mechanical extrapolations of past data for education only. They are not predictions, targets or recommendations, and actual returns can fall outside this range.
            </p>
          </details>
        </>
      )}
    </section>
  );
}

function Input({ label, value, unsigned }: { label: string; value: number | null; unsigned?: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-black/25 px-3 py-2">
      <span>{label}</span>
      <span className={clsx("num font-medium", value === null ? "text-muted" : unsigned ? "text-slate-200" : value >= 0 ? "text-up" : "text-down")}>
        {value === null ? "—" : `${!unsigned && value > 0 ? "+" : ""}${value.toFixed(1)}%`}
      </span>
    </div>
  );
}
