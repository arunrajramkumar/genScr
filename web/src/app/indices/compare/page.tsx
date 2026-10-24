"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import clsx from "clsx";
import { LINE_COLORS } from "@/components/chartColors";
import { SectionNote } from "@/components/Legal";
import { ErrorNote, Loading, PageLoading } from "@/components/ui";
import { api } from "@/lib/api";
import { changeClass, fmtNum, fmtPct } from "@/lib/format";
import type { IndexSummary } from "@/lib/types";
import { ValuationBar } from "@/components/ValuationBar";

const CompareChart = dynamic(() => import("@/components/PriceChart").then((m) => m.CompareChart), { ssr: false, loading: () => <Loading /> });

type Row = { summary: IndexSummary; series: { time: string; value: number }[] };
const METRICS: [keyof IndexSummary, string, boolean][] = [
  ["return_1m", "1 month", true], ["return_ytd", "YTD", true], ["return_1y", "1 year", true],
  ["cagr_3y", "3Y CAGR", true], ["cagr_5y", "5Y CAGR", true], ["pe", "P/E", false], ["pb", "P/B", false], ["div_yield", "Dividend yield", false],
];

function Compare() {
  const params = useSearchParams();
  const slugs = params.get("slugs") ?? "nifty-50,nifty-midcap-150,nifty-smallcap-250";
  const [years, setYears] = useState(3);
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setRows(null);
    api<Row[]>(`/indices/compare?slugs=${encodeURIComponent(slugs)}&years=${years}`).then(setRows).catch((e) => setError(e.message));
  }, [slugs, years]);

  if (error) return <ErrorNote message={error} hint={<Link href="/indices" className="text-accent">Pick indices from the list</Link>} />;
  if (!rows) return <PageLoading />;
  const series = Object.fromEntries(rows.map((r) => [r.summary.name, r.series]));

  return (
    <div className="space-y-6">
      <div>
        <Link href="/indices" className="text-xs text-muted hover:text-white">← All indices</Link>
        <h1 className="mt-1 text-2xl font-bold text-white">Compare indices</h1>
      </div>
      <section className="panel p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-3 text-xs">
            {rows.map((r, i) => <span key={r.summary.slug} className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: LINE_COLORS[i % LINE_COLORS.length] }} />{r.summary.name}</span>)}
          </div>
          <div className="seg">
            {[1, 3, 5, 10].map((y) => <button key={y} onClick={() => setYears(y)} aria-pressed={years === y} className={clsx("seg-btn", years === y && "seg-btn-active")}>{y}Y</button>)}
          </div>
        </div>
        <CompareChart series={series} />
        <p className="mt-1 text-[11px] text-muted">Growth of 100 over the selected period (price index, weekly points).</p>
      </section>

      <section className="panel overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left">
              <th scope="col" className="px-4 py-3 text-xs font-medium text-muted">Metric</th>
              {rows.map((r, i) => (
                <th scope="col" key={r.summary.slug} className="px-4 py-3 text-right">
                  <Link href={`/indices/${r.summary.slug}`} className="inline-flex items-center gap-1.5 font-semibold text-white hover:text-accent">
                    <span className="h-2 w-2 rounded-full" style={{ background: LINE_COLORS[i % LINE_COLORS.length] }} />{r.summary.name}
                  </Link>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {METRICS.map(([k, label, signed]) => (
              <tr key={k} className="table-row">
                <th scope="row" className="px-4 py-2 text-left font-normal text-muted">{label}</th>
                {rows.map((r) => {
                  const v = r.summary[k] as number | null;
                  return <td key={r.summary.slug} className={clsx("num px-4 py-2 text-right", signed && changeClass(v))}>{signed ? fmtPct(v) : k === "div_yield" ? (v ? `${fmtNum(v)}%` : "—") : fmtNum(v)}</td>;
                })}
              </tr>
            ))}
            <tr className="table-row">
              <th scope="row" className="px-4 py-2 text-left font-normal text-muted">P/E vs own history</th>
              {rows.map((r) => <td key={r.summary.slug} className="px-4 py-2 text-right"><ValuationBar pct={r.summary.pe_percentile} /></td>)}
            </tr>
          </tbody>
        </table>
      </section>
      <SectionNote>Source: NSE daily index files. Price returns, excluding dividends. Historical comparison only, not a recommendation.</SectionNote>
    </div>
  );
}

export default function CompareIndicesPage() {
  return (
    <Suspense fallback={<PageLoading />}>
      <Compare />
    </Suspense>
  );
}
