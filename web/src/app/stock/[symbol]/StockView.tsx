"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import clsx from "clsx";
import { ArrowDownRight, ArrowUpRight, GitCompare } from "lucide-react";
import AnimatedNumber from "@/components/AnimatedNumber";
import DidYouKnow from "@/components/DidYouKnow";
import { SectionNote, StaleDataBanner } from "@/components/Legal";
import PriceCagr from "@/components/PriceCagr";
import Signals from "@/components/Signals";
import { ErrorNote, Loading, RangeBar, ScoreBadge, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { changeClass, fmtCr, fmtNum, fmtPct, fmtPrice, fmtVolume, toNum } from "@/lib/format";
import { ENABLE_PROJECTIONS } from "@/lib/site";
import type { Candle, Fundamental, Stock } from "@/lib/types";

// Chart-heavy sections load on demand so the page shell renders fast.
const StockChart = dynamic(() => import("@/components/PriceChart").then((m) => m.StockChart), { ssr: false, loading: () => <Loading /> });
const ReturnsCalculator = dynamic(() => import("@/components/ReturnsCalculator"), { ssr: false, loading: () => <Loading /> });
const Outlook = dynamic(() => import("@/components/Outlook"), { ssr: false });

/** Symbol from the URL. Static hosting serves one prebuilt shell for every /stock/<SYMBOL>, so read the real path. */
function useSymbol(): string | null {
  const params = useParams<{ symbol: string }>();
  const [symbol, setSymbol] = useState<string | null>(null);
  useEffect(() => {
    const [first, second] = window.location.pathname.split("/").filter(Boolean);
    const raw = first === "stock" && second && second !== "_" ? second : params.symbol;
    setSymbol(raw && raw !== "_" ? decodeURIComponent(raw).toUpperCase() : null);
  }, [params.symbol]);
  return symbol;
}

const FIN_ROWS = [
  ["Revenue", "revenue"], ["Operating profit", "operating_profit"], ["Net profit", "net_profit"], ["EPS (₹)", "eps"],
  ["Total assets", "total_assets"], ["Equity", "total_equity"], ["Debt", "total_debt"], ["Cash from ops", "cfo"],
] as const;

export default function StockView() {
  const symbol = useSymbol();
  const [stock, setStock] = useState<Stock | null>(null);
  const [prices, setPrices] = useState<Candle[] | null>(null);
  const [funds, setFunds] = useState<Fundamental[]>([]);
  const [quarters, setQuarters] = useState<Fundamental[]>([]);
  const [finView, setFinView] = useState<"FY" | "Q">("FY");
  const [peers, setPeers] = useState<Stock[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!symbol) return;
    const s = encodeURIComponent(symbol);
    setError(null);
    setStock(null);
    setPrices(null);
    api<Stock>(`/stocks/${s}`).then(setStock).catch((e) => setError(e.message));
    api<Candle[]>(`/stocks/${s}/prices?range=max`).then(setPrices).catch(() => setPrices([]));
    api<Fundamental[]>(`/stocks/${s}/fundamentals?period=FY&limit=6`).then(setFunds).catch(() => setFunds([]));
    api<Fundamental[]>(`/stocks/${s}/fundamentals?period=Q&limit=8`).then(setQuarters).catch(() => setQuarters([]));
    api<Stock[]>(`/stocks/${s}/peers`).then(setPeers).catch(() => setPeers([]));
  }, [symbol]);

  if (error) return <ErrorNote message={error} />;
  if (!stock) return <Loading />;

  const change = toNum(stock.change_pct);
  const up = (change ?? 0) >= 0;
  const close = toNum(stock.close);
  const rsi = toNum(stock.rsi_14);
  const finRows = (finView === "FY" ? funds : quarters).slice().reverse();

  return (
    <div className="space-y-6">
      <StaleDataBanner asOf={stock.as_of} />
      {/* Hero */}
      <section className="relative animate-fade-up overflow-hidden rounded-3xl border border-white/[0.06] p-6">
        <div className="grid-bg pointer-events-none absolute inset-0" />
        <div className={clsx("pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full blur-3xl", up ? "bg-up/15" : "bg-down/15")} />
        <div className="relative flex flex-wrap items-end justify-between gap-6">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-4xl font-bold tracking-tight text-white">{stock.symbol}</h1>
              {stock.sector && <Link href={`/screener?sector=${encodeURIComponent(stock.sector)}`} className="chip">{stock.sector}</Link>}
              <span className="num rounded-full border border-line px-2 py-0.5 text-[10px] text-muted">NSE</span>
            </div>
            <div className="mt-1 text-muted">{stock.name}</div>
            <div className="mt-4"><Signals stock={stock} /></div>
          </div>
          <div className="text-right">
            <div className="num text-5xl font-bold tracking-tight text-white">
              {close !== null ? <AnimatedNumber value={close} format={(v) => fmtPrice(v)} /> : "—"}
            </div>
            <div className="mt-2 flex items-center justify-end gap-2">
              <span className={clsx("num inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-sm font-semibold", up ? "bg-up/15 text-up shadow-glow-up" : "bg-down/15 text-down shadow-glow-down")}>
                {up ? <ArrowUpRight className="h-4 w-4" /> : <ArrowDownRight className="h-4 w-4" />}
                {fmtPct(stock.change_pct)}
              </span>
              <span className="text-xs text-muted">
                <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse-dot rounded-full bg-gold align-middle" />
                EOD {stock.as_of ? new Date(stock.as_of).toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : ""}
              </span>
            </div>
            <div className="mt-4 w-64 max-w-full">
              <RangeBar low={stock.low_52w} high={stock.high_52w} value={stock.close} />
              <div className="num mt-1.5 flex justify-between text-[10px] text-muted">
                <span>52W L {fmtPrice(stock.low_52w)}</span><span>52W H {fmtPrice(stock.high_52w)}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Chart + Did you know */}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section className="panel min-w-0 p-4">
          <div className="mb-1 flex justify-end">
            <Link href={`/compare?symbols=${encodeURIComponent(stock.symbol)}${peers[0] ? "," + encodeURIComponent(peers[0].symbol) : ""}`} className="btn text-xs">
              <GitCompare className="h-3.5 w-3.5" /> Compare with peers
            </Link>
          </div>
          {prices === null ? <Loading /> : prices.length ? <StockChart data={prices} /> : <div className="py-16 text-center text-sm text-muted">No price history</div>}
        </section>
        <DidYouKnow symbol={stock.symbol} />
      </div>

      {/* Key stats */}
      <section className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
        <Stat label="Market cap" value={fmtCr(stock.market_cap)} />
        <Stat label="P/E" value={fmtNum(stock.pe)} />
        <Stat label="P/B" value={fmtNum(stock.pb)} />
        <Stat label="Dividend yield" value={fmtPct(stock.dividend_yield, false)} sub={toNum(stock.dividend_yield) === null ? "No dividends in last FY" : "Last FY dividends paid"} />
        <Stat label="ROE" value={fmtPct(stock.roe, false)} />
        <Stat label="ROCE" value={fmtPct(stock.roce, false)} />
        <Stat label="Debt / Equity" value={fmtNum(stock.debt_to_equity)} />
        <Stat label="Net margin" value={fmtPct(stock.net_margin, false)} />
        <Stat label="Revenue growth" value={<span className={changeClass(stock.revenue_growth_yoy)}>{fmtPct(stock.revenue_growth_yoy)}</span>} sub="YoY" />
        <Stat label="Profit growth" value={<span className={changeClass(stock.profit_growth_yoy)}>{fmtPct(stock.profit_growth_yoy)}</span>} sub="YoY" />
        <Stat label="1M return" value={<span className={changeClass(stock.return_1m)}>{fmtPct(stock.return_1m)}</span>} />
        <Stat label="1Y return" value={<span className={changeClass(stock.return_1y)}>{fmtPct(stock.return_1y)}</span>} />
        <Stat label="Avg volume" value={fmtVolume(stock.avg_volume_20d)} sub="20 days" />
        <Stat label="Turnover" value={fmtCr(stock.turnover)} sub="Latest session" />
      </section>

      {prices && prices.length > 0 && <PriceCagr prices={prices} />}

      {/* What-if + outlook */}
      {prices && prices.length > 0 && (
        <>
          <ReturnsCalculator symbol={stock.symbol} prices={prices} />
          {ENABLE_PROJECTIONS && <Outlook prices={prices} funds={funds} />}
        </>
      )}

      {/* Scores / technicals / peers */}
      <section className="grid gap-4 lg:grid-cols-3">
        <div className="panel p-5">
          <div className="label mb-4">Quality & risk scores</div>
          <div className="space-y-4 text-sm">
            <div className="flex items-center justify-between gap-3">
              <div><div className="text-white">Piotroski F-Score</div><div className="text-xs text-muted">9-point financial strength check</div></div>
              <ScoreBadge kind="piotroski" value={stock.piotroski_f} />
            </div>
            <div className="flex items-center justify-between gap-3">
              <div><div className="text-white">Altman Z&apos;&apos;</div><div className="text-xs text-muted">Bankruptcy-risk model (not for banks)</div></div>
              <ScoreBadge kind="altman" value={stock.altman_z} />
            </div>
          </div>
        </div>
        <div className="panel p-5">
          <div className="label mb-4">Technicals</div>
          <div className="space-y-2.5 text-sm">
            <Row label="RSI (14)">
              <span className={clsx("num", rsi !== null && (rsi > 70 || rsi < 30) ? "text-gold" : "text-white")}>
                {fmtNum(stock.rsi_14)}{rsi !== null && (rsi > 70 ? " · above 70" : rsi < 30 ? " · below 30" : "")}
              </span>
            </Row>
            {rsi !== null && (
              <div className="relative h-1.5 rounded-full bg-gradient-to-r from-slate-500/60 via-slate-700 to-slate-500/60">
                <div className="absolute top-1/2 h-3 w-1 -translate-y-1/2 rounded bg-white" style={{ left: `${rsi}%` }} />
              </div>
            )}
            <Row label="50 DMA"><span className="num">{fmtPrice(stock.sma_50)}</span></Row>
            <Row label="200 DMA"><span className="num">{fmtPrice(stock.sma_200)}</span></Row>
            <Row label="From 52W high"><span className={clsx("num", changeClass(stock.pct_from_52w_high))}>{fmtPct(stock.pct_from_52w_high)}</span></Row>
          </div>
        </div>
        <div className="panel p-5">
          <div className="label mb-3">Peers{stock.sector ? ` · ${stock.sector}` : ""}</div>
          <ul className="space-y-0.5 text-sm">
            {peers.map((p) => (
              <li key={p.symbol}>
                <Link href={`/stock/${encodeURIComponent(p.symbol)}`} className="flex items-center justify-between rounded-lg px-2 py-1.5 hover:bg-white/5">
                  <span className="font-medium text-white">{p.symbol}</span>
                  <span className="num text-xs text-muted">{fmtCr(p.market_cap)} · <span className={changeClass(p.return_1y)}>{fmtPct(p.return_1y)} 1Y</span></span>
                </Link>
              </li>
            ))}
            {peers.length === 0 && <li className="text-muted">No sector peers available</li>}
          </ul>
        </div>
      </section>

      <SectionNote>
        Figures and scores are computed mechanically from exchange data and company filings for education only. They are not
        a rating, research report or recommendation to buy, sell or hold {stock.symbol}.
      </SectionNote>

      {/* Financials */}
      <section className="panel overflow-x-auto p-5">
        <div className="mb-3 flex items-center justify-between">
          <div className="label">Financials (₹ Cr)</div>
          <div className="seg">
            <button onClick={() => setFinView("FY")} className={clsx("seg-btn", finView === "FY" && "seg-btn-active")}>Annual</button>
            <button onClick={() => setFinView("Q")} className={clsx("seg-btn", finView === "Q" && "seg-btn-active")}>Quarterly</button>
          </div>
        </div>
        {finRows.length === 0 ? (
          <div className="text-sm text-muted">No financials loaded for this company yet.</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted">
                <th className="py-2 pr-4 font-medium">Metric</th>
                {finRows.map((f) => (
                  <th key={f.period_end} className="num py-2 pr-4 text-right font-medium">
                    {finView === "FY" ? `FY${f.period_end.slice(2, 4)}` : new Date(f.period_end).toLocaleDateString("en-IN", { month: "short", year: "2-digit" })}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {FIN_ROWS.map(([label, key]) => (
                <tr key={key} className="table-row">
                  <td className="py-2 pr-4 text-muted">{label}</td>
                  {finRows.map((f, i) => {
                    const v = toNum(f[key]), prev = i > 0 ? toNum(finRows[i - 1][key]) : null;
                    const trend = v !== null && prev !== null && prev !== 0 ? (v > prev ? "text-up/80" : v < prev ? "text-down/80" : "") : "";
                    return <td key={f.period_end} className={clsx("num py-2 pr-4 text-right", trend)}>{fmtNum(f[key], key === "eps" ? 2 : 0)}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="flex items-center justify-between"><span className="text-muted">{label}</span>{children}</div>;
}
