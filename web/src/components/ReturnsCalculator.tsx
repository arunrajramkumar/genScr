"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import YearSlider from "./YearSlider";
import { Calculator, Repeat, Wallet } from "lucide-react";
import { GrowthChart } from "./PriceChart";
import { availableYears, lumpsum, sip } from "@/lib/returns";
import { changeClass, fmtPct } from "@/lib/format";
import type { Candle } from "@/lib/types";

const inr = (v: number) => `₹${Math.round(v).toLocaleString("en-IN")}`;
const PRESETS = [5_000, 10_000, 25_000, 1_00_000];

export default function ReturnsCalculator({ symbol, prices }: { symbol: string; prices: Candle[] }) {
  const maxYears = availableYears(prices);
  const [mode, setMode] = useState<"lumpsum" | "sip">("lumpsum");
  const [amount, setAmount] = useState(10_000);
  const [years, setYears] = useState(Math.min(5, Math.max(1, maxYears)));

  const result = useMemo(
    () => (maxYears < 1 ? null : mode === "lumpsum" ? lumpsum(prices, years, amount) : sip(prices, years, amount)),
    [prices, years, amount, mode, maxYears],
  );

  const quick = useMemo(
    () => [1, 3, 5, 10].filter((y) => y <= maxYears).map((y) => ({ y, r: mode === "lumpsum" ? lumpsum(prices, y, amount) : sip(prices, y, amount) })),
    [prices, amount, mode, maxYears],
  );

  if (maxYears < 1) {
    return (
      <section className="panel p-5">
        <Header />
        <p className="mt-3 text-sm text-muted">Needs at least 1 year of price history. Run a backfill to enable this.</p>
      </section>
    );
  }

  const positive = (result?.gain ?? 0) >= 0;

  return (
    <section className="panel overflow-hidden p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Header />
        <div className="seg">
          <button onClick={() => setMode("lumpsum")} className={clsx("seg-btn inline-flex items-center gap-1.5", mode === "lumpsum" && "seg-btn-active")}>
            <Wallet className="h-3.5 w-3.5" /> One-time
          </button>
          <button onClick={() => setMode("sip")} className={clsx("seg-btn inline-flex items-center gap-1.5", mode === "sip" && "seg-btn-active")}>
            <Repeat className="h-3.5 w-3.5" /> Monthly SIP
          </button>
        </div>
      </div>

      <div className="mt-5 grid gap-6 lg:grid-cols-[1fr_1.3fr]">
        <div className="space-y-6">
          <div>
            <div className="label mb-2">{mode === "lumpsum" ? "Amount invested" : "Monthly SIP amount"}</div>
            <div className="flex items-center gap-2 rounded-xl border border-line bg-black/30 px-3 py-2 focus-within:border-accent/60">
              <span className="text-muted">₹</span>
              <input
                type="number" min={100} step={500} value={amount}
                onChange={(e) => setAmount(Math.max(0, Number(e.target.value) || 0))}
                className="num w-full bg-transparent text-lg text-white outline-none"
                aria-label="Investment amount"
              />
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {PRESETS.map((p) => (
                <button key={p} onClick={() => setAmount(p)} className={clsx("chip num", amount === p && "border-accent/60 text-white")}>{inr(p)}</button>
              ))}
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-baseline justify-between">
              <span className="label">Invested</span>
              <span className="num text-lg font-semibold text-white">{years} {years === 1 ? "year" : "years"} ago</span>
            </div>
            <YearSlider value={years} max={maxYears} onChange={setYears} />
          </div>

          {result && (
            <div className={clsx("rounded-2xl border p-4", positive ? "border-up/25 bg-up/[0.06] shadow-glow-up" : "border-down/25 bg-down/[0.06] shadow-glow-down")}>
              <div className="text-xs text-muted">
                {mode === "lumpsum" ? `${inr(amount)} invested` : `${inr(amount)}/month from`} on{" "}
                {new Date(result.startDate).toLocaleDateString("en-IN", { dateStyle: "medium" })} would be worth
              </div>
              <div className={clsx("num mt-1 text-3xl font-bold", positive ? "text-up" : "text-down")}>{inr(result.value)}</div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                <Mini label="Invested" value={inr(result.invested)} />
                <Mini label={positive ? "Gain" : "Loss"} value={<span className={changeClass(result.gain)}>{fmtPct(result.gainPct)}</span>} />
                <Mini label={mode === "sip" ? "XIRR" : "CAGR"} value={<span className={changeClass(result.cagr)}>{result.cagr === null ? "—" : `${result.cagr.toFixed(1)}%`}</span>} />
              </div>
            </div>
          )}
        </div>

        <div>
          {result && <GrowthChart series={result.series} positive={positive} />}
          {quick.length > 0 && (
            <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {quick.map(({ y, r }) => (
                <button key={y} onClick={() => setYears(y)} className={clsx("panel panel-hover p-3 text-left", y === years && "border-accent/40")}>
                  <div className="label">{y}Y ago</div>
                  <div className="num mt-1 text-sm font-semibold text-white">{r ? inr(r.value) : "—"}</div>
                  <div className={clsx("num text-xs", changeClass(r?.cagr ?? null))}>{r?.cagr != null ? `${r.cagr.toFixed(1)}% p.a.` : ""}</div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <p className="mt-4 text-[11px] text-muted">
        Based on {symbol}&apos;s split/bonus-adjusted closing prices. Price return only (dividends, taxes and charges not included). Past performance does not indicate future returns.
      </p>
    </section>
  );
}

function Header() {
  return (
    <div className="flex items-center gap-2">
      <Calculator className="h-5 w-5 text-accent" />
      <h2 className="text-lg font-semibold text-white">What if you had invested?</h2>
    </div>
  );
}

function Mini({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg bg-black/25 px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-wider text-muted">{label}</div>
      <div className="num text-sm font-semibold text-white">{value}</div>
    </div>
  );
}
