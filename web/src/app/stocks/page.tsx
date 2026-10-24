"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { BookA, Search } from "lucide-react";
import { ErrorNote, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { changeClass, fmtPct, fmtPrice } from "@/lib/format";

type Row = { symbol: string; name: string; sector: string | null; close: number | null; change_pct: number | null };
type Browse = { letter: string; by: "name" | "symbol"; stocks: Row[]; truncated: boolean; letters: Record<string, number> };

const LETTERS = [..."ABCDEFGHIJKLMNOPQRSTUVWXYZ", "0-9"];

function Directory() {
  const router = useRouter();
  const params = useSearchParams();
  const letter = LETTERS.includes(params.get("letter") ?? "") ? params.get("letter")! : "A";
  const by = params.get("by") === "symbol" ? "symbol" : "name";
  const [data, setData] = useState<Browse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    setError(null);
    setFilter("");
    api<Browse>(`/stocks/browse?letter=${encodeURIComponent(letter)}&by=${by}`).then(setData).catch((e) => setError(e.message));
  }, [letter, by]);

  const go = (l: string, b = by) => router.replace(`/stocks?letter=${encodeURIComponent(l)}${b === "symbol" ? "&by=symbol" : ""}`, { scroll: false });

  const rows = useMemo(() => {
    const f = filter.trim().toLowerCase();
    const list = data?.letter === letter ? data.stocks : [];
    return f ? list.filter((r) => r.symbol.toLowerCase().includes(f) || r.name.toLowerCase().includes(f)) : list;
  }, [data, letter, filter]);

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-cyan-400 text-bg"><BookA className="h-6 w-6" /></div>
        <div>
          <h1 className="text-2xl font-bold text-white">Stocks A–Z</h1>
          <p className="mt-1 text-sm text-muted">Every NSE-listed company, alphabetically. Pick a letter, then a company to open its page.</p>
        </div>
      </div>

      <div className="panel z-30 space-y-3 p-3 md:sticky md:top-[66px]">
        <nav className="flex flex-wrap gap-1" aria-label="Browse by first letter">
          {LETTERS.map((l) => {
            const n = data?.letters[l] ?? 0;
            const active = l === letter;
            return (
              <button key={l} onClick={() => go(l)} disabled={!!data && n === 0} aria-current={active ? "page" : undefined}
                title={data ? `${n} ${by === "symbol" ? "symbols" : "companies"}` : undefined}
                className={clsx("num min-w-[2.25rem] rounded-lg px-2 py-1.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-30",
                  active ? "bg-accent text-bg" : "bg-white/[0.04] text-slate-200 hover:bg-white/10 hover:text-white")}>
                {l}
              </button>
            );
          })}
        </nav>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div className="seg">
            {(["name", "symbol"] as const).map((b) => (
              <button key={b} onClick={() => go(letter, b)} className={clsx("seg-btn", by === b && "seg-btn-active")}>By {b === "name" ? "company name" : "NSE symbol"}</button>
            ))}
          </div>
          <label className="relative min-w-[200px] flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-2 h-3.5 w-3.5 text-muted" />
            <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder={`Narrow down within "${letter}"…`}
              className="w-full rounded-lg border border-line bg-panel py-1.5 pl-8 pr-2 text-sm text-white outline-none focus:border-accent/60" aria-label="Filter this letter" />
          </label>
          {data && <span className="text-muted"><span className="num text-white">{rows.length}</span> of {data.letters[letter] ?? 0}</span>}
        </div>
      </div>

      {error && <ErrorNote message={error} />}
      {!data && !error && <Loading />}
      {data && (
        rows.length ? (
          <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {rows.map((r) => (
              <li key={r.symbol}>
                <Link href={`/stock/${encodeURIComponent(r.symbol)}`} className="panel panel-hover flex items-center justify-between gap-3 px-3 py-2.5">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-white">{by === "symbol" ? r.symbol : r.name}</div>
                    <div className="truncate text-[11px] text-muted">{by === "symbol" ? r.name : r.symbol}{r.sector && <span className="text-slate-500"> · {r.sector}</span>}</div>
                  </div>
                  <div className="shrink-0 text-right">
                    <div className="num text-sm text-white">{fmtPrice(r.close)}</div>
                    <div className={clsx("num text-[11px]", changeClass(r.change_pct))}>{fmtPct(r.change_pct)}</div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        ) : <p className="panel p-6 text-center text-sm text-muted">No companies match “{filter}” under {letter}.</p>
      )}
      {data?.truncated && <p className="text-center text-xs text-muted">Showing the first {data.stocks.length}. Use the box above or the search bar to find the rest.</p>}
    </div>
  );
}

export default function StocksPage() {
  return (
    <Suspense fallback={<Loading />}>
      <Directory />
    </Suspense>
  );
}
