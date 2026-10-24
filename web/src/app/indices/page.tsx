"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { GitCompare, Layers } from "lucide-react";
import { SectionNote, StaleDataBanner } from "@/components/Legal";
import { ErrorNote, PageLoading } from "@/components/ui";
import { api } from "@/lib/api";
import { changeClass, fmtNum, fmtPct } from "@/lib/format";
import type { IndexSummary } from "@/lib/types";
import { ValuationBar } from "@/components/ValuationBar";

const ORDER = ["Broad market", "Sector & theme", "Strategy & factor", "Volatility", "Bonds & rates"];

export default function IndicesPage() {
  const router = useRouter();
  const [data, setData] = useState<IndexSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [sort, setSort] = useState<{ key: keyof IndexSummary; dir: 1 | -1 }>({ key: "return_1y", dir: -1 });

  useEffect(() => {
    api<IndexSummary[]>("/indices").then(setData).catch((e) => setError(e.message));
  }, []);

  const groups = useMemo(() => {
    const g = new Map<string, IndexSummary[]>();
    (data ?? []).forEach((i) => g.set(i.category, [...(g.get(i.category) ?? []), i]));
    for (const [k, v] of g) {
      g.set(k, [...v].sort((a, b) => ((a[sort.key] as number) ?? -1e9) < ((b[sort.key] as number) ?? -1e9) ? -sort.dir : sort.dir));
    }
    return ORDER.filter((k) => g.has(k)).map((k) => [k, g.get(k)!] as const);
  }, [data, sort]);

  const toggle = (slug: string) => setSelected((s) => (s.includes(slug) ? s.filter((x) => x !== slug) : s.length >= 6 ? s : [...s, slug]));
  const head = (key: keyof IndexSummary, label: string) => (
    <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-medium">
      <button onClick={() => setSort((s) => ({ key, dir: s.key === key ? (s.dir === 1 ? -1 : 1) : -1 }))} className={clsx("hover:text-white", sort.key === key && "text-accent")}>{label}</button>
    </th>
  );

  if (error) return <ErrorNote message={error} />;
  if (!data) return <PageLoading />;
  const nifty = data.find((i) => i.name === "Nifty 50");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-white"><Layers className="h-6 w-6 text-accent" /> Indices</h1>
          <p className="mt-1 text-sm text-muted">Every NSE index: returns over time and how expensive it is compared with its own history.</p>
        </div>
        {selected.length >= 2 && (
          <button onClick={() => router.push(`/indices/compare?slugs=${selected.join(",")}`)} className="btn-primary text-xs">
            <GitCompare className="h-3.5 w-3.5" /> Compare {selected.length} indices
          </button>
        )}
      </div>
      <StaleDataBanner asOf={nifty?.as_of} />

      {nifty && (
        <section className="grid grid-cols-2 gap-3 md:grid-cols-5">
          {data.filter((i) => ["Nifty 50", "Nifty Next 50", "Nifty Midcap 150", "Nifty Smallcap 250", "Nifty Bank"].includes(i.name)).map((i) => (
            <Link key={i.slug} href={`/indices/${i.slug}`} className="panel panel-hover p-4">
              <div className="label truncate">{i.name}</div>
              <div className="num mt-1 text-lg font-semibold text-white">{fmtNum(i.close)}</div>
              <div className={clsx("num text-xs", changeClass(i.change_pct))}>{fmtPct(i.change_pct)} today · <span className={changeClass(i.return_1y)}>{fmtPct(i.return_1y)} 1Y</span></div>
            </Link>
          ))}
        </section>
      )}

      {groups.map(([cat, items]) => (
        <section key={cat} className="panel overflow-hidden">
          <h2 className="border-b border-line px-4 py-3 text-sm font-semibold text-white">{cat} <span className="font-normal text-muted">({items.length})</span></h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted">
                  <th scope="col" className="w-8 px-3 py-2"><span className="sr-only">Select to compare</span></th>
                  <th scope="col" className="px-2 py-2 font-medium">Index</th>
                  {head("close", "Level")}
                  {head("change_pct", "Today")}
                  {head("return_1m", "1M")}
                  {head("return_ytd", "YTD")}
                  {head("return_1y", "1Y")}
                  {head("cagr_3y", "3Y CAGR")}
                  {head("cagr_5y", "5Y CAGR")}
                  {head("pe", "P/E")}
                  <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-medium" title="Where today's P/E sits within this index's own history">P/E vs own history</th>
                  {head("div_yield", "Yield")}
                </tr>
              </thead>
              <tbody>
                {items.map((i) => (
                  <tr key={i.slug} className="table-row">
                    <td className="px-3 py-2">
                      <input type="checkbox" checked={selected.includes(i.slug)} onChange={() => toggle(i.slug)} aria-label={`Select ${i.name} to compare`} className="accent-[#7c9cff]" />
                    </td>
                    <td className="px-2 py-2"><Link href={`/indices/${i.slug}`} className="font-medium text-white hover:text-accent">{i.name}</Link></td>
                    <td className="num px-3 py-2 text-right">{fmtNum(i.close)}</td>
                    {(["change_pct", "return_1m", "return_ytd", "return_1y", "cagr_3y", "cagr_5y"] as const).map((k) => (
                      <td key={k} className={clsx("num px-3 py-2 text-right", changeClass(i[k]))}>{fmtPct(i[k])}</td>
                    ))}
                    <td className="num px-3 py-2 text-right">{i.pe ? fmtNum(i.pe, 1) : "—"}</td>
                    <td className="px-3 py-2 text-right"><ValuationBar pct={i.pe_percentile} /></td>
                    <td className="num px-3 py-2 text-right">{i.div_yield ? `${fmtNum(i.div_yield)}%` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
      <SectionNote>
        Source: NSE daily index files (level, P/E, P/B and dividend yield as published by NSE). Returns are price returns of the index,
        excluding dividends. &quot;P/E vs own history&quot; shows where today&apos;s P/E sits among all trading days in our data; it describes the
        past and is not a valuation call. BSE indices such as the Sensex are not yet available.
      </SectionNote>
    </div>
  );
}
