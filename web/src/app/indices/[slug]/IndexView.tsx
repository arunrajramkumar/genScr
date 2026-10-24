"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { Layers } from "lucide-react";
import { SectionNote, StaleDataBanner } from "@/components/Legal";
import { ErrorNote, Loading, PageLoading, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { changeClass, fmtCr, fmtNum, fmtPct, fmtPrice } from "@/lib/format";
import type { IndexDetail } from "@/lib/types";

const LineChart = dynamic(() => import("@/components/PriceChart").then((m) => m.SimpleLineChart), { ssr: false, loading: () => <Loading /> });
const UnderwaterChart = dynamic(() => import("@/components/PriceChart").then((m) => m.UnderwaterChart), { ssr: false, loading: () => <Loading /> });

const RANGES = [{ id: "1Y", days: 366 }, { id: "3Y", days: 1097 }, { id: "5Y", days: 1827 }, { id: "MAX", days: 1e9 }];

function useSlug(): string | null {
  const params = useParams<{ slug: string }>();
  const [slug, setSlug] = useState<string | null>(null);
  useEffect(() => {
    const [first, second] = window.location.pathname.split("/").filter(Boolean);
    const raw = first === "indices" && second && second !== "_" ? second : params.slug;
    setSlug(raw && raw !== "_" ? decodeURIComponent(raw) : null);
  }, [params.slug]);
  return slug;
}

export default function IndexView() {
  const slug = useSlug();
  const [d, setD] = useState<IndexDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [range, setRange] = useState("5Y");
  const [metric, setMetric] = useState<"pe" | "pb" | "div_yield">("pe");

  useEffect(() => {
    if (!slug) return;
    api<IndexDetail>(`/indices/${encodeURIComponent(slug)}`).then(setD).catch((e) => setError(e.message));
  }, [slug]);

  const series = useMemo(() => {
    if (!d?.prices.length) return [];
    const days = RANGES.find((r) => r.id === range)!.days;
    const end = new Date(d.prices[d.prices.length - 1].time).getTime();
    return d.prices.filter((p) => end - new Date(p.time).getTime() <= days * 86_400_000);
  }, [d, range]);

  const val = useMemo(() => {
    const pts = (d?.valuation ?? []).filter((v) => v[metric] !== null).map((v) => ({ time: v.time, value: v[metric] as number }));
    const values = pts.map((p) => p.value).sort((a, b) => a - b);
    const q = (p: number) => values[Math.floor((values.length - 1) * p)];
    return { pts, min: values[0], max: values[values.length - 1], median: values.length ? q(0.5) : null, last: pts[pts.length - 1]?.value };
  }, [d, metric]);

  if (error) return <ErrorNote message={error} />;
  if (!d) return <PageLoading />;
  const s = d.summary;
  const rangeRet = series.length > 1 ? (series[series.length - 1].value / series[0].value - 1) * 100 : null;
  const worst = d.risk?.worst_drawdowns[0];

  return (
    <div className="space-y-6">
      <StaleDataBanner asOf={s.as_of} />
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link href="/indices" className="text-xs text-muted hover:text-white">← All indices</Link>
          <h1 className="mt-1 flex items-center gap-2 text-3xl font-bold text-white"><Layers className="h-7 w-7 text-accent" />{s.name}</h1>
          <div className="mt-1 text-sm text-muted">{s.category} · NSE index · data since {new Date(s.since).getFullYear()}</div>
        </div>
        <div className="text-right">
          <div className="num text-4xl font-bold text-white">{fmtNum(s.close)}</div>
          <div className={clsx("num text-sm", changeClass(s.change_pct))}>{fmtPct(s.change_pct)} <span className="text-muted">· {new Date(s.as_of).toLocaleDateString("en-IN", { dateStyle: "medium" })}</span></div>
        </div>
      </section>

      <section className="panel p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div className="seg">
            {RANGES.map((r) => <button key={r.id} onClick={() => setRange(r.id)} aria-pressed={range === r.id} className={clsx("seg-btn", range === r.id && "seg-btn-active")}>{r.id}</button>)}
          </div>
          {rangeRet !== null && <span className={clsx("num rounded-md px-2 py-1 text-xs font-semibold", rangeRet >= 0 ? "bg-up/10 text-up" : "bg-down/10 text-down")}>{range} {fmtPct(rangeRet)}</span>}
        </div>
        <LineChart series={series} positive={(rangeRet ?? 0) >= 0} />
      </section>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-8">
        <Stat label="1 month" value={<span className={changeClass(s.return_1m)}>{fmtPct(s.return_1m)}</span>} />
        <Stat label="YTD" value={<span className={changeClass(s.return_ytd)}>{fmtPct(s.return_ytd)}</span>} />
        <Stat label="1 year" value={<span className={changeClass(s.return_1y)}>{fmtPct(s.return_1y)}</span>} />
        <Stat label="3Y CAGR" value={<span className={changeClass(s.cagr_3y)}>{fmtPct(s.cagr_3y)}</span>} />
        <Stat label="5Y CAGR" value={<span className={changeClass(s.cagr_5y)}>{fmtPct(s.cagr_5y)}</span>} />
        <Stat label="P/E" value={s.pe ? fmtNum(s.pe, 1) : "—"} sub={s.pe_percentile !== null ? `higher than ${s.pe_percentile.toFixed(0)}% of days` : undefined} />
        <Stat label="P/B" value={s.pb ? fmtNum(s.pb) : "—"} />
        <Stat label="Dividend yield" value={s.div_yield ? `${fmtNum(s.div_yield)}%` : "—"} />
      </section>

      {val.pts.length > 10 && (
        <section className="panel p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-white">Valuation history</h2>
            <div className="seg">
              {(["pe", "pb", "div_yield"] as const).map((m) => (
                <button key={m} onClick={() => setMetric(m)} aria-pressed={metric === m} className={clsx("seg-btn", metric === m && "seg-btn-active")}>{m === "pe" ? "P/E" : m === "pb" ? "P/B" : "Dividend yield"}</button>
              ))}
            </div>
          </div>
          <p className="mt-1 text-sm text-slate-300">
            Now <span className="num font-semibold text-white">{fmtNum(val.last)}</span>; range since {new Date(d.valuation[0].time).getFullYear()}:{" "}
            <span className="num">{fmtNum(val.min)}</span> – <span className="num">{fmtNum(val.max)}</span>, median <span className="num">{fmtNum(val.median)}</span>.
          </p>
          <LineChart series={val.pts} positive median={val.median ?? undefined} />
        </section>
      )}

      {d.risk && (
        <section className="panel p-5">
          <h2 className="text-lg font-semibold text-white">Drawdowns</h2>
          <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Worst fall" value={<span className="text-down">{fmtPct(worst?.depth_pct)}</span>} sub={worst ? `${worst.peak_date.slice(0, 7)} → ${worst.trough_date.slice(0, 7)}` : undefined} />
            <Stat label="Recovery" value={worst?.days_to_recover ? `${Math.round(worst.days_to_recover / 30)} months` : "Not yet"} />
            <Stat label="Now vs peak" value={<span className={changeClass(d.risk.current_drawdown_pct)}>{fmtPct(d.risk.current_drawdown_pct)}</span>} />
            <Stat label="Volatility (1Y)" value={fmtPct(d.risk.volatility_1y_pct, false)} />
          </div>
          <div className="mt-4"><UnderwaterChart series={d.risk.underwater} /></div>
        </section>
      )}

      {d.constituents.length > 0 && (
        <section className="panel overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
            <h2 className="text-lg font-semibold text-white">Constituents <span className="text-sm font-normal text-muted">({d.constituents.length})</span></h2>
            <div className="flex flex-wrap gap-1.5">
              {d.sector_mix.slice(0, 6).map(([name, n]) => <span key={name} className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-slate-300">{name} <span className="num text-muted">{n}</span></span>)}
            </div>
          </div>
          <div className="max-h-[560px] overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-panel text-left text-xs text-muted">
                <tr>
                  <th scope="col" className="px-4 py-2 font-medium">Company</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Price</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Today</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Market cap</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">P/E</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">ROE</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">1Y</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Yield</th>
                </tr>
              </thead>
              <tbody>
                {d.constituents.map((c) => (
                  <tr key={c.symbol} className="table-row">
                    <td className="px-4 py-2"><Link href={`/stock/${encodeURIComponent(c.symbol)}`} className="font-medium text-white hover:text-accent">{c.symbol}</Link><div className="max-w-[220px] truncate text-xs text-muted">{c.name}</div></td>
                    <td className="num px-3 py-2 text-right">{fmtPrice(c.close)}</td>
                    <td className={clsx("num px-3 py-2 text-right", changeClass(c.change_pct))}>{fmtPct(c.change_pct)}</td>
                    <td className="num px-3 py-2 text-right">{fmtCr(c.market_cap)}</td>
                    <td className="num px-3 py-2 text-right">{fmtNum(c.pe, 1)}</td>
                    <td className="num px-3 py-2 text-right">{fmtPct(c.roe, false)}</td>
                    <td className={clsx("num px-3 py-2 text-right", changeClass(c.return_1y))}>{fmtPct(c.return_1y)}</td>
                    <td className="num px-3 py-2 text-right">{fmtPct(c.dividend_yield, false)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      <SectionNote>Source: NSE daily index files and constituent lists. Index returns are price returns (excluding dividends). Valuation figures are as published by NSE. Historical data only; not a valuation call or recommendation.</SectionNote>
    </div>
  );
}
