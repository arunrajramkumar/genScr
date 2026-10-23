"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { ArrowDown, ArrowUp, Play } from "lucide-react";
import { ErrorNote, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { changeClass, fmtField } from "@/lib/format";
import type { FieldMeta, Preset, ScreenResponse } from "@/lib/types";

const COLUMNS = ["close", "change_pct", "market_cap", "pe", "dividend_yield", "roe", "roce", "debt_to_equity", "revenue_growth_yoy", "piotroski_f", "return_1y", "rsi_14"];

function Screener() {
  const params = useSearchParams();
  const sector = params.get("sector");
  const [query, setQuery] = useState(params.get("q") ?? "market_cap > 1000 and roe > 15");
  const [presets, setPresets] = useState<Preset[]>([]);
  const [fields, setFields] = useState<Record<string, FieldMeta>>({});
  const [sort, setSort] = useState({ field: "market_cap", order: "desc" as "asc" | "desc" });
  const [data, setData] = useState<ScreenResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Preset[]>("/screener/presets").then(setPresets).catch(() => {});
    api<Record<string, FieldMeta>>("/screener/fields").then(setFields).catch(() => {});
  }, []);

  const run = useCallback(
    (q: string, s = sort) => {
      setLoading(true);
      setError(null);
      api<ScreenResponse>("/screener", {
        method: "POST",
        body: JSON.stringify({ query: q, sector, sort: s.field, order: s.order, limit: 200 }),
      })
        .then(setData)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    },
    [sector, sort],
  );

  useEffect(() => {
    run(query); // re-run when the sector filter in the URL changes
  }, [sector]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleSort = (field: string) => {
    const next = { field, order: sort.field === field && sort.order === "desc" ? ("asc" as const) : ("desc" as const) };
    setSort(next);
    run(query, next);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Stock screener{sector && <span className="text-muted"> · {sector}</span>}</h1>
        <p className="mt-1 text-sm text-muted">Write conditions joined with <code className="text-slate-300">and</code>. Press Ctrl/⌘ + Enter to run.</p>
      </div>

      <div className="flex flex-wrap gap-2">
        {presets.map((p) => (
          <button key={p.id} title={p.description} className="chip" onClick={() => { setQuery(p.query); run(p.query); }}>
            {p.name}
          </button>
        ))}
      </div>

      <div className="panel p-4">
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run(query); }}
          rows={3}
          spellCheck={false}
          className="num w-full resize-y bg-transparent text-sm text-white outline-none"
          aria-label="Screener query"
        />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
          <details className="text-xs text-muted">
            <summary className="cursor-pointer hover:text-white">Available fields</summary>
            <div className="mt-2 flex max-w-3xl flex-wrap gap-1.5">
              {Object.entries(fields).map(([k, f]) => (
                <button key={k} className="rounded border border-line px-1.5 py-0.5 font-mono hover:text-white" onClick={() => setQuery((q) => `${q.trim()} and ${k} > `)} title={`${f.label} (${f.unit || "value"})`}>
                  {k}
                </button>
              ))}
            </div>
          </details>
          <button className="btn-primary" onClick={() => run(query)} disabled={loading}>
            <Play className="h-4 w-4" /> Run screen
          </button>
        </div>
      </div>

      {error && <ErrorNote message={error} />}
      {loading && !data && <Loading />}

      {data && (
        <div className="panel overflow-x-auto">
          <div className="px-4 py-3 text-sm text-muted">{data.count} stocks match{data.count === 200 ? " (showing first 200)" : ""}</div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-y border-line text-left text-xs text-muted">
                <th className="px-4 py-2 font-medium">Company</th>
                {COLUMNS.map((c) => (
                  <th key={c} className="cursor-pointer whitespace-nowrap px-3 py-2 text-right font-medium hover:text-white" onClick={() => toggleSort(c)}>
                    <span className="inline-flex items-center gap-1">
                      {fields[c]?.label ?? c}
                      {sort.field === c && (sort.order === "desc" ? <ArrowDown className="h-3 w-3" /> : <ArrowUp className="h-3 w-3" />)}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className={clsx(loading && "opacity-50")}>
              {data.results.map((s) => (
                <tr key={s.symbol} className="table-row">
                  <td className="px-4 py-2">
                    <Link href={`/stock/${encodeURIComponent(s.symbol)}`} className="font-medium text-white hover:text-accent">{s.symbol}</Link>
                    <div className="max-w-[220px] truncate text-xs text-muted">{s.name}</div>
                  </td>
                  {COLUMNS.map((c) => {
                    const v = s[c as keyof typeof s] as string | number | null;
                    return (
                      <td key={c} className={clsx("num whitespace-nowrap px-3 py-2 text-right", (c === "change_pct" || c === "return_1y") && changeClass(v))}>
                        {fmtField(v, fields[c]?.unit ?? "")}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function ScreenerPage() {
  return (
    <Suspense fallback={<Loading />}>
      <Screener />
    </Suspense>
  );
}
