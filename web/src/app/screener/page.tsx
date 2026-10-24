"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { ArrowDown, ArrowUp, Check, Link2, Play } from "lucide-react";
import { SectionNote } from "@/components/Legal";
import { ErrorNote, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { changeClass, fmtField, toNum } from "@/lib/format";
import type { FieldMeta, Preset, ScreenResponse } from "@/lib/types";

const COLUMNS = ["close", "change_pct", "market_cap", "pe", "dividend_yield", "roe", "roce", "debt_to_equity", "revenue_growth_yoy", "piotroski_f", "return_1y", "rsi_14"];

function median(values: (number | null)[]): number | null {
  const v = values.filter((x): x is number => x !== null).sort((a, b) => a - b);
  if (!v.length) return null;
  const m = Math.floor(v.length / 2);
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
}

function Screener() {
  const router = useRouter();
  const params = useSearchParams();
  const [copied, setCopied] = useState(false);
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
        .then((d) => {
          // Keep the screen in the URL so it can be bookmarked or shared.
          const qs = new URLSearchParams();
          qs.set("q", q);
          if (sector) qs.set("sector", sector);
          router.replace(`/screener?${qs.toString()}`, { scroll: false });
          return d;
        })
        .then(setData)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    },
    [sector, sort, router],
  );

  const summary = useMemo(() => {
    const rows = data?.results ?? [];
    const pick = (k: keyof (typeof rows)[number]) => median(rows.map((r) => toNum(r[k] as never)));
    const sectors = new Map<string, number>();
    rows.forEach((r) => r.sector && sectors.set(r.sector, (sectors.get(r.sector) ?? 0) + 1));
    return {
      pe: pick("pe"), roe: pick("roe"), ret: pick("return_1y"), dy: pick("dividend_yield"),
      sectors: Array.from(sectors.entries()).sort((a, b) => b[1] - a[1]).slice(0, 6),
    };
  }, [data]);

  const share = () => {
    navigator.clipboard?.writeText(window.location.href).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

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

      <SectionNote>Presets are example filters on public data, not stock picks or recommendations. Results change daily.</SectionNote>

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
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
            <div className="text-sm text-muted">{data.count} stocks match{data.count === 200 ? " (showing first 200)" : ""}</div>
            <button onClick={share} className="btn text-xs">
              {copied ? <Check className="h-3.5 w-3.5 text-up" /> : <Link2 className="h-3.5 w-3.5" />} {copied ? "Link copied" : "Share this screen"}
            </button>
          </div>
          {data.count > 0 && (
            <div className="grid gap-3 border-b border-line px-4 py-3 text-xs sm:grid-cols-[auto_1fr]">
              <div className="flex flex-wrap gap-4">
                <span className="text-muted">Median P/E <span className="num text-white">{summary.pe?.toFixed(1) ?? "—"}</span></span>
                <span className="text-muted">Median ROE <span className="num text-white">{summary.roe !== null ? `${summary.roe.toFixed(1)}%` : "—"}</span></span>
                <span className="text-muted">Median 1Y return <span className={clsx("num", changeClass(summary.ret))}>{summary.ret !== null ? `${summary.ret.toFixed(1)}%` : "—"}</span></span>
                <span className="text-muted">Median yield <span className="num text-white">{summary.dy !== null ? `${summary.dy.toFixed(2)}%` : "—"}</span></span>
              </div>
              <div className="flex flex-wrap gap-1.5 sm:justify-end">
                {summary.sectors.map(([name, n]) => (
                  <span key={name} className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-slate-300">{name} <span className="num text-muted">{n}</span></span>
                ))}
              </div>
            </div>
          )}
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
