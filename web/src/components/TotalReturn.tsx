"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import clsx from "clsx";
import { Gift, Layers, Scissors, Sparkles, Wallet } from "lucide-react";
import { SectionNote } from "./Legal";
import { Loading } from "./ui";
import { api } from "@/lib/api";
import { useInView } from "@/lib/useInView";
import type { TotalReturnResponse } from "@/lib/types";

const ReturnLinesChart = dynamic(() => import("./PriceChart").then((m) => m.ReturnLinesChart), { ssr: false, loading: () => <Loading /> });

const inr = (v: number, d = 0) => `₹${v.toLocaleString("en-IN", { maximumFractionDigits: d, minimumFractionDigits: d })}`;
const day = (d: string) => new Date(d).toLocaleDateString("en-IN", { dateStyle: "medium" });
const AMOUNTS = [10_000, 50_000, 1_00_000];

export default function TotalReturn({ symbol }: { symbol: string }) {
  const { ref, inView } = useInView<HTMLElement>();
  const [years, setYears] = useState(5);
  const [amount, setAmount] = useState(10_000);
  const [maxYears, setMaxYears] = useState(10);
  const [data, setData] = useState<TotalReturnResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showLedger, setShowLedger] = useState(false);

  useEffect(() => {
    if (!inView) return;
    setError(null);
    api<TotalReturnResponse>(`/stocks/${encodeURIComponent(symbol)}/total-return?years=${years}&amount=${amount}`)
      .then((d) => {
        setData(d);
        setMaxYears(Math.max(1, d.available_years));
        if (years > d.available_years && d.available_years >= 1) setYears(d.available_years);
      })
      .catch((e) => setError(e.message));
  }, [inView, symbol, years, amount]);

  const best = data?.reinvested;
  const up = (best?.gain_pct ?? 0) >= 0;

  return (
    <section ref={ref} className="panel overflow-hidden p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-gold" />
          <div>
            <h2 className="text-lg font-semibold text-white">Past returns</h2>
            <p className="text-xs text-muted">Including dividends, bonus shares and splits</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {AMOUNTS.map((a) => (
            <button key={a} onClick={() => setAmount(a)} className={clsx("chip num", amount === a && "border-accent/60 text-white")}>{inr(a)}</button>
          ))}
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-2 flex items-baseline justify-between">
          <span className="label">Invested</span>
          <span className="num text-lg font-semibold text-white">{years} year{years > 1 ? "s" : ""} ago</span>
        </div>
        <input type="range" min={1} max={maxYears} value={Math.min(years, maxYears)} onChange={(e) => setYears(Number(e.target.value))} className="slider" aria-label="Years ago" />
      </div>

      {error && <p className="mt-4 text-sm text-muted">{error}</p>}
      {!data && !error && <Loading />}

      {data && best && (
        <>
          <p className="mt-5 text-sm text-slate-300">
            <span className="num font-semibold text-white">{inr(data.amount)}</span> invested in {symbol} on{" "}
            <span className="text-white">{day(data.start_date)}</span> would be worth
          </p>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            <Outcome icon={<Layers className="h-4 w-4" />} title="Price only" note="Ignoring dividends" value={data.price_only.total_value} cagr={data.price_only.cagr} tone="muted" />
            <Outcome icon={<Wallet className="h-4 w-4" />} title="With dividends as cash" note={`${inr(data.dividends_received)} received`} value={data.with_dividends.total_value} cagr={data.with_dividends.cagr} tone="accent" />
            <Outcome icon={<Sparkles className="h-4 w-4" />} title="Dividends reinvested" note="Bought more shares each time" value={best.total_value} cagr={best.cagr} tone={up ? "up" : "down"} highlight />
          </div>

          {data.benchmark && (
            <p className="mt-3 text-xs text-muted">
              For context, the same {inr(data.amount)} in the {data.benchmark.name} index over the same dates would be{" "}
              <span className="num text-slate-200">{inr(data.benchmark.value)}</span>
              {data.benchmark.cagr !== null && <span className="num"> ({data.benchmark.cagr > 0 ? "+" : ""}{data.benchmark.cagr.toFixed(1)}% p.a.)</span>}
              , price index, excluding index dividends.
            </p>
          )}

          <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_1.2fr]">
            <div className="space-y-2 text-sm">
              <div className="label mb-1">Where the money came from</div>
              <Row icon={<Wallet className="h-4 w-4 text-muted" />} label={`Bought ${data.initial_shares.toLocaleString("en-IN", { maximumFractionDigits: 2 })} shares @ ${inr(data.buy_price, 2)}`} value={inr(data.amount)} />
              {data.bonus_split_shares > 0 && (
                <Row icon={<Gift className="h-4 w-4 text-gold" />} label="Free shares from bonuses & splits" value={`+${data.bonus_split_shares.toLocaleString("en-IN", { maximumFractionDigits: 2 })} shares`} />
              )}
              <Row icon={<Layers className="h-4 w-4 text-muted" />} label={`${data.with_dividends.shares.toLocaleString("en-IN", { maximumFractionDigits: 2 })} shares @ ${inr(data.end_price, 2)} today`} value={inr(data.with_dividends.market_value)} />
              <Row icon={<Wallet className="h-4 w-4 text-accent" />} label={`Dividends received (${data.dividend_payments} payments)`} value={`+${inr(data.dividends_received)}`} />
              <div className="flex items-center justify-between border-t border-line pt-2 font-semibold text-white">
                <span>Total (dividends as cash)</span>
                <span className="num">{inr(data.with_dividends.total_value)}</span>
              </div>
              {data.events.length > 0 && (
                <button onClick={() => setShowLedger((v) => !v)} className="mt-2 text-xs text-accent hover:underline">
                  {showLedger ? "Hide" : "Show"} every event ({data.events.length})
                </button>
              )}
            </div>
            <ReturnLinesChart series={data.series} />
          </div>

          {showLedger && (
            <div className="mt-4 max-h-72 overflow-auto rounded-xl border border-line">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-panel text-left text-muted">
                  <tr><th className="px-3 py-2">Date</th><th className="px-3 py-2">Event</th><th className="px-3 py-2 text-right">Effect</th><th className="px-3 py-2 text-right">Shares after</th></tr>
                </thead>
                <tbody>
                  {data.events.map((e, i) => (
                    <tr key={i} className="table-row">
                      <td className="num px-3 py-1.5">{day(e.date)}</td>
                      <td className="px-3 py-1.5">
                        <span className="inline-flex items-center gap-1.5">
                          {e.kind === "dividend" ? <Wallet className="h-3.5 w-3.5 text-accent" /> : e.kind === "bonus" ? <Gift className="h-3.5 w-3.5 text-gold" /> : <Scissors className="h-3.5 w-3.5 text-gold" />}
                          {e.kind === "dividend" ? `Dividend ₹${e.per_share}/share` : e.kind === "bonus" ? `Bonus ${e.detail}` : `Split ${e.detail}`}
                        </span>
                      </td>
                      <td className="num px-3 py-1.5 text-right">{e.kind === "dividend" ? `+${inr(e.received ?? 0)}` : `+${(e.shares_added ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })} sh`}</td>
                      <td className="num px-3 py-1.5 text-right">{e.shares_after.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="mt-4 space-y-1">
            {data.caveats.map((c) => <SectionNote key={c}>{c}</SectionNote>)}
            <SectionNote>
              Historical calculation from actual NSE closing prices and recorded corporate actions. Fractional shares, no taxes or
              charges; reinvestment at the ex-date close. Rights issues and buybacks are not modelled. Past performance does not
              indicate future returns.
            </SectionNote>
          </div>
        </>
      )}
    </section>
  );
}

function Outcome({ icon, title, note, value, cagr, tone, highlight }: {
  icon: React.ReactNode; title: string; note: string; value: number; cagr: number | null; tone: "muted" | "accent" | "up" | "down"; highlight?: boolean;
}) {
  return (
    <div className={clsx("rounded-2xl border p-4", highlight ? (tone === "down" ? "border-down/30 bg-down/[0.06] shadow-glow-down" : "border-up/30 bg-up/[0.06] shadow-glow-up") : "border-white/[0.06] bg-black/25")}>
      <div className={clsx("flex items-center gap-1.5 text-xs font-semibold", tone === "up" ? "text-up" : tone === "down" ? "text-down" : tone === "accent" ? "text-accent" : "text-muted")}>{icon}{title}</div>
      <div className={clsx("num mt-1.5 text-2xl font-bold", highlight ? (tone === "down" ? "text-down" : "text-up") : "text-white")}>{inr(value)}</div>
      <div className="mt-1 flex justify-between text-[11px] text-muted"><span>{note}</span>{cagr !== null && <span className="num">{cagr > 0 ? "+" : ""}{cagr.toFixed(1)}% p.a.</span>}</div>
    </div>
  );
}

function Row({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="flex items-center gap-2 text-slate-300">{icon}{label}</span>
      <span className="num text-white">{value}</span>
    </div>
  );
}
