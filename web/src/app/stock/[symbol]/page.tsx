"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import clsx from "clsx";
import { GitCompare } from "lucide-react";
import { PriceChart } from "@/components/PriceChart";
import { ErrorNote, Loading, RangeBar, ScoreBadge, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { changeClass, fmtCr, fmtNum, fmtPct, fmtPrice, fmtVolume, toNum } from "@/lib/format";
import type { Candle, Fundamental, Stock } from "@/lib/types";

const RANGES = ["1m", "6m", "1y", "3y", "5y", "max"] as const;

function trendNote(s: Stock): string | null {
  const c = toNum(s.close), s50 = toNum(s.sma_50), s200 = toNum(s.sma_200);
  if (c === null || s50 === null || s200 === null) return null;
  if (c > s50 && s50 > s200) return "Price above 50 & 200 DMA: uptrend";
  if (c < s50 && s50 < s200) return "Price below 50 & 200 DMA: downtrend";
  return "Mixed trend vs moving averages";
}

export default function StockPage() {
  const { symbol: raw } = useParams<{ symbol: string }>();
  const symbol = decodeURIComponent(raw).toUpperCase();
  const [stock, setStock] = useState<Stock | null>(null);
  const [prices, setPrices] = useState<Candle[] | null>(null);
  const [range, setRange] = useState<(typeof RANGES)[number]>("1y");
  const [funds, setFunds] = useState<Fundamental[]>([]);
  const [peers, setPeers] = useState<Stock[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const s = encodeURIComponent(symbol);
    setError(null);
    api<Stock>(`/stocks/${s}`).then(setStock).catch((e) => setError(e.message));
    api<Fundamental[]>(`/stocks/${s}/fundamentals?period=FY&limit=6`).then(setFunds).catch(() => setFunds([]));
    api<Stock[]>(`/stocks/${s}/peers`).then(setPeers).catch(() => setPeers([]));
  }, [symbol]);

  useEffect(() => {
    setPrices(null);
    api<Candle[]>(`/stocks/${encodeURIComponent(symbol)}/prices?range=${range}`).then(setPrices).catch(() => setPrices([]));
  }, [symbol, range]);

  if (error) return <ErrorNote message={error} />;
  if (!stock) return <Loading />;

  const trend = trendNote(stock);
  const rsi = toNum(stock.rsi_14);

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight text-white">{stock.symbol}</h1>
            {stock.sector && <span className="chip">{stock.sector}</span>}
          </div>
          <div className="mt-1 text-muted">{stock.name}</div>
        </div>
        <div className="text-right">
          <div className="num text-3xl font-semibold text-white">{fmtPrice(stock.close)}</div>
          <div className={clsx("num text-sm", changeClass(stock.change_pct))}>
            {fmtPct(stock.change_pct)} <span className="text-muted">· close {stock.as_of ?? ""}</span>
          </div>
        </div>
      </section>

      <section className="panel p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex gap-1">
            {RANGES.map((r) => (
              <button key={r} onClick={() => setRange(r)} className={clsx("rounded-md px-2.5 py-1 text-xs uppercase", r === range ? "bg-white/10 text-white" : "text-muted hover:text-white")}>
                {r}
              </button>
            ))}
          </div>
          <Link href={`/compare?symbols=${encodeURIComponent(stock.symbol)}${peers[0] ? "," + encodeURIComponent(peers[0].symbol) : ""}`} className="btn">
            <GitCompare className="h-4 w-4" /> Compare
          </Link>
        </div>
        {prices === null ? <Loading /> : prices.length ? <PriceChart data={prices} /> : <div className="py-16 text-center text-sm text-muted">No price history</div>}
        <div className="mt-4 grid gap-2 sm:grid-cols-[auto_1fr_auto] sm:items-center">
          <span className="num text-xs text-muted">52W L {fmtPrice(stock.low_52w)}</span>
          <RangeBar low={stock.low_52w} high={stock.high_52w} value={stock.close} />
          <span className="num text-xs text-muted">52W H {fmtPrice(stock.high_52w)}</span>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
        <Stat label="Market cap" value={fmtCr(stock.market_cap)} />
        <Stat label="P/E" value={fmtNum(stock.pe)} />
        <Stat label="P/B" value={fmtNum(stock.pb)} />
        <Stat label="ROE" value={fmtPct(stock.roe, false)} />
        <Stat label="ROCE" value={fmtPct(stock.roce, false)} />
        <Stat label="Debt / Equity" value={fmtNum(stock.debt_to_equity)} />
        <Stat label="Net margin" value={fmtPct(stock.net_margin, false)} />
        <Stat label="Revenue growth" value={fmtPct(stock.revenue_growth_yoy)} sub="YoY" />
        <Stat label="Profit growth" value={fmtPct(stock.profit_growth_yoy)} sub="YoY" />
        <Stat label="1M return" value={<span className={changeClass(stock.return_1m)}>{fmtPct(stock.return_1m)}</span>} />
        <Stat label="1Y return" value={<span className={changeClass(stock.return_1y)}>{fmtPct(stock.return_1y)}</span>} />
        <Stat label="Avg volume" value={fmtVolume(stock.avg_volume_20d)} sub="20 days" />
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="panel p-5">
          <div className="label mb-3">Quality & risk scores</div>
          <div className="space-y-4 text-sm">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-white">Piotroski F-Score</div>
                <div className="text-xs text-muted">9-point financial strength check</div>
              </div>
              <ScoreBadge kind="piotroski" value={stock.piotroski_f} />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-white">Altman Z&apos;&apos;</div>
                <div className="text-xs text-muted">Bankruptcy-risk model (EM variant)</div>
              </div>
              <ScoreBadge kind="altman" value={stock.altman_z} />
            </div>
          </div>
        </div>
        <div className="panel p-5">
          <div className="label mb-3">Technicals</div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-muted">RSI (14)</span><span className={clsx("num", rsi !== null && (rsi > 70 ? "text-down" : rsi < 30 ? "text-up" : "text-white"))}>{fmtNum(stock.rsi_14)}{rsi !== null && (rsi > 70 ? " · overbought" : rsi < 30 ? " · oversold" : "")}</span></div>
            <div className="flex justify-between"><span className="text-muted">50 DMA</span><span className="num">{fmtPrice(stock.sma_50)}</span></div>
            <div className="flex justify-between"><span className="text-muted">200 DMA</span><span className="num">{fmtPrice(stock.sma_200)}</span></div>
            <div className="flex justify-between"><span className="text-muted">From 52W high</span><span className={clsx("num", changeClass(stock.pct_from_52w_high))}>{fmtPct(stock.pct_from_52w_high)}</span></div>
            {trend && <div className="pt-2 text-xs text-muted">{trend}</div>}
          </div>
        </div>
        <div className="panel p-5">
          <div className="label mb-3">Peers{stock.sector ? ` · ${stock.sector}` : ""}</div>
          <ul className="space-y-1 text-sm">
            {peers.map((p) => (
              <li key={p.symbol}>
                <Link href={`/stock/${encodeURIComponent(p.symbol)}`} className="flex justify-between rounded px-1 py-1 hover:bg-white/5">
                  <span className="text-white">{p.symbol}</span>
                  <span className="num text-muted">{fmtCr(p.market_cap)} · P/E {fmtNum(p.pe, 1)}</span>
                </Link>
              </li>
            ))}
            {peers.length === 0 && <li className="text-muted">No sector peers available</li>}
          </ul>
        </div>
      </section>

      <section className="panel overflow-x-auto p-5">
        <div className="label mb-3">Annual financials (₹ Cr)</div>
        {funds.length === 0 ? (
          <div className="text-sm text-muted">No financials loaded for this company yet.</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted">
                <th className="py-2 pr-4 font-medium">Metric</th>
                {funds.map((f) => <th key={f.period_end} className="num py-2 pr-4 text-right font-medium">{f.period_end.slice(0, 7)}</th>)}
              </tr>
            </thead>
            <tbody>
              {([
                ["Revenue", "revenue"], ["Operating profit", "operating_profit"], ["Net profit", "net_profit"], ["EPS (₹)", "eps"],
                ["Total assets", "total_assets"], ["Equity", "total_equity"], ["Debt", "total_debt"], ["Cash from ops", "cfo"],
              ] as const).map(([label, key]) => (
                <tr key={key} className="table-row">
                  <td className="py-2 pr-4 text-muted">{label}</td>
                  {funds.map((f) => <td key={f.period_end} className="num py-2 pr-4 text-right">{fmtNum(f[key], key === "eps" ? 2 : 0)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
