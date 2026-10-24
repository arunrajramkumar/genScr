"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import clsx from "clsx";
import { ArrowDownRight, ArrowUpRight, Flame, SlidersHorizontal } from "lucide-react";
import SearchBox from "@/components/SearchBox";
import TickerTape from "@/components/TickerTape";
import { StaleDataBanner } from "@/components/Legal";
import { ErrorNote, PageLoading, heatClass } from "@/components/ui";
import { api } from "@/lib/api";
import { changeClass, fmtCr, fmtPct, fmtPrice } from "@/lib/format";
import type { Overview, Stock } from "@/lib/types";

function MoverList({ title, icon, rows, metric }: { title: string; icon: React.ReactNode; rows: Stock[]; metric: "change" | "turnover" }) {
  return (
    <div className="panel panel-hover p-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
        {icon} {title}
      </div>
      <ul className="space-y-1">
        {rows.map((s) => (
          <li key={s.symbol}>
            <Link href={`/stock/${encodeURIComponent(s.symbol)}`} className="flex items-center justify-between rounded-lg px-2 py-1.5 hover:bg-white/5">
              <div className="min-w-0">
                <div className="text-sm font-medium text-white">{s.symbol}</div>
                <div className="truncate text-xs text-muted">{s.name}</div>
              </div>
              <div className="text-right">
                <div className="num text-sm">{fmtPrice(s.close)}</div>
                <div className={clsx("num text-xs", metric === "change" ? changeClass(s.change_pct) : "text-muted")}>
                  {metric === "change" ? fmtPct(s.change_pct) : fmtCr(s.turnover)}
                </div>
              </div>
            </Link>
          </li>
        ))}
        {rows.length === 0 && <li className="text-sm text-muted">No data</li>}
      </ul>
    </div>
  );
}

export default function Home() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Overview>("/market/overview").then(setData).catch((e) => setError(e.message));
  }, []);

  const b = data?.breadth;
  const total = b ? b.advances + b.declines + b.unchanged : 0;

  return (
    <div className="space-y-10">
      <section className="relative mx-auto max-w-3xl animate-fade-up pt-6 text-center">
        <div className="grid-bg pointer-events-none absolute -inset-x-40 -inset-y-10" />
        <h1 className="bg-gradient-to-r from-white via-slate-200 to-accent bg-clip-text text-4xl font-bold tracking-tight text-transparent sm:text-5xl">
          Every NSE stock, clearly analysed.
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-muted">
          Fundamentals, quality scores, technicals and comparisons, built on public exchange data. Free and transparent.
        </p>
        <div className="mx-auto mt-8 max-w-2xl">
          <SearchBox large />
        </div>
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          <Link href="/screener" className="chip inline-flex items-center gap-1.5">
            <SlidersHorizontal className="h-3 w-3" /> Open screener
          </Link>
          <Link href="/compare?symbols=TCS,INFY,HCLTECH" className="chip">Compare TCS · INFY · HCLTECH</Link>
        </div>
      </section>

      {data && (
        <div className="-mx-4">
          <TickerTape stocks={[...data.active, ...data.gainers, ...data.losers]} />
        </div>
      )}

      {error && (
        <ErrorNote
          message={`Couldn't load market data: ${error}`}
          hint={<>Make sure the API is running and data is loaded. See the README Quick start (<code>make ingest</code>).</>}
        />
      )}
      {!data && !error && <PageLoading />}

      {data && !data.as_of && (
        <ErrorNote message="No market data yet." hint={<>Run <code>make ingest</code> to load the latest NSE bhavcopy and compute metrics.</>} />
      )}

      {data?.as_of && b && (
        <>
          <StaleDataBanner asOf={data.as_of} />
          <section className="panel p-5">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <div className="label">Market breadth · {new Date(data.as_of).toLocaleDateString("en-IN", { dateStyle: "medium" })}</div>
                <div className="mt-1 text-sm text-muted">
                  <span className="num text-up">{b.advances}</span> advances · <span className="num text-down">{b.declines}</span> declines ·{" "}
                  <span className="num">{b.unchanged}</span> unchanged
                </div>
              </div>
              <div className="text-sm text-muted">
                <span className="num text-up">{b.new_highs}</span> at 52W high · <span className="num text-down">{b.new_lows}</span> at 52W low
              </div>
            </div>
            {total > 0 && (
              <div className="mt-4 flex h-2 overflow-hidden rounded-full">
                <div className="bg-up" style={{ width: `${(b.advances / total) * 100}%` }} />
                <div className="bg-slate-600" style={{ width: `${(b.unchanged / total) * 100}%` }} />
                <div className="bg-down" style={{ width: `${(b.declines / total) * 100}%` }} />
              </div>
            )}
          </section>

          <section className="grid gap-4 md:grid-cols-3">
            <MoverList title="Top gainers" icon={<ArrowUpRight className="h-4 w-4 text-up" />} rows={data.gainers} metric="change" />
            <MoverList title="Top losers" icon={<ArrowDownRight className="h-4 w-4 text-down" />} rows={data.losers} metric="change" />
            <MoverList title="Most active (turnover)" icon={<Flame className="h-4 w-4 text-amber-400" />} rows={data.active} metric="turnover" />
          </section>

          {data.sectors.length > 0 && (
            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">Sector heatmap</h2>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
                {data.sectors.map((s) => (
                  <Link
                    key={s.sector}
                    href={`/screener?sector=${encodeURIComponent(s.sector)}`}
                    className={clsx("rounded-xl p-3 transition hover:ring-1 hover:ring-white/30", heatClass(s.avg_change))}
                  >
                    <div className="truncate text-sm font-medium text-white">{s.sector}</div>
                    <div className="num mt-1 text-lg font-semibold text-white">{fmtPct(s.avg_change)}</div>
                    <div className="text-xs text-white/70">{s.stocks} stocks · 1Y {fmtPct(s.avg_return_1y)}</div>
                  </Link>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
