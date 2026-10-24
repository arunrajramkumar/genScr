"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { ArrowDown, ArrowUp, Check, ChevronDown, Code2, GitCompare, Link2, Plus, ScatterChart, Search, Table2, X } from "lucide-react";
import { SectionNote } from "@/components/Legal";
import { ErrorNote, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { changeClass, fmtField, toNum } from "@/lib/format";
import type { Preset, Stock } from "@/lib/types";

const ScreenerScatter = dynamic(() => import("@/components/ScreenerScatter"), { ssr: false, loading: () => <Loading /> });

type Op = ">" | ">=" | "<" | "<=";
interface Filter { id: number; field: string; op: Op; value: string }
interface FieldInfo { label: string; unit: string; higher_is_better: boolean | null; description: string; group: string }
interface Dist { count: number; p10?: number; p25?: number; p50?: number; p75?: number; p90?: number; hist_lo?: number; hist_hi?: number; hist?: number[] }
interface Stats { fields: Record<string, Dist>; sectors: string[]; universe: number }
interface Result { count: number; total: number; universe: number; results: Stock[] }

const CORE = ["close", "change_pct", "market_cap", "pe", "roe", "return_1y", "dividend_yield"];
const OPS: Op[] = [">", ">=", "<", "<="];
const OP_WORDS: Record<Op, string> = { ">": "above", ">=": "at least", "<": "below", "<=": "at most" };
const COND = /^\s*([a-z_0-9/]+)\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)\s*$/i;
const SIGNED = ["change_pct", "return_1y", "return_1m", "cagr_3y", "cagr_5y"];

let nextId = 1;
const toQuery = (fs: Filter[]) =>
  fs.filter((f) => f.value.trim() !== "" && !isNaN(Number(f.value))).map((f) => `${f.field} ${f.op} ${f.value}`).join(" and ");

function fromQuery(q: string, known: Record<string, FieldInfo>): Filter[] | null {
  const parts = q.split(/\s+and\s+|\n/i).filter((p) => p.trim());
  const out: Filter[] = [];
  for (const p of parts) {
    const m = COND.exec(p);
    if (!m || !known[m[1].toLowerCase()]) return null;
    out.push({ id: nextId++, field: m[1].toLowerCase(), op: m[2] as Op, value: m[3] });
  }
  return out;
}

function median(values: (number | null)[]): number | null {
  const v = values.filter((x): x is number => x !== null).sort((a, b) => a - b);
  if (!v.length) return null;
  const m = Math.floor(v.length / 2);
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
}

/** Share of the market passing a threshold, estimated from the histogram. */
function passShare(d: Dist | undefined, op: Op, value: number): number | null {
  if (!d?.hist || d.hist_lo === undefined || d.hist_hi === undefined || !d.count) return null;
  const width = (d.hist_hi - d.hist_lo) / d.hist.length;
  let pass = 0;
  d.hist.forEach((n, i) => {
    const mid = d.hist_lo! + width * (i + 0.5);
    if (op === ">" || op === ">=" ? mid >= value : mid <= value) pass += n;
  });
  const inHist = d.hist.reduce((a, b) => a + b, 0);
  return inHist ? (pass / inHist) * 100 : null;
}

function Histogram({ d, op, value }: { d?: Dist; op: Op; value: number | null }) {
  if (!d?.hist || d.hist_lo === undefined || d.hist_hi === undefined) return null;
  const max = Math.max(1, ...d.hist);
  const span = d.hist_hi - d.hist_lo || 1;
  const pos = value === null ? null : Math.min(100, Math.max(0, ((value - d.hist_lo) / span) * 100));
  return (
    <div className="relative mt-2 flex h-10 items-end gap-px" aria-hidden>
      {d.hist.map((n, i) => {
        const mid = d.hist_lo! + (span / d.hist!.length) * (i + 0.5);
        const passing = value !== null && (op === ">" || op === ">=" ? mid >= value : mid <= value);
        return <div key={i} className={clsx("flex-1 rounded-t-sm", passing ? "bg-accent/70" : "bg-white/10")} style={{ height: `${Math.max(4, (n / max) * 100)}%` }} />;
      })}
      {pos !== null && <div className="absolute bottom-0 top-0 w-0.5 bg-gold" style={{ left: `${pos}%` }} />}
    </div>
  );
}

function FieldPicker({ fields, onPick, onClose }: { fields: Record<string, FieldInfo>; onPick: (f: string) => void; onClose: () => void }) {
  const [q, setQ] = useState("");
  const groups = useMemo(() => {
    const g = new Map<string, string[]>();
    Object.entries(fields).forEach(([k, f]) => {
      if (q && !`${f.label} ${f.description} ${k}`.toLowerCase().includes(q.toLowerCase())) return;
      g.set(f.group, [...(g.get(f.group) ?? []), k]);
    });
    return Array.from(g.entries());
  }, [fields, q]);
  return (
    <div className="panel absolute left-0 top-full z-30 mt-2 w-[min(92vw,420px)] bg-panel p-2 shadow-2xl">
      <div className="flex items-center gap-2 rounded-lg border border-line px-2 py-1.5">
        <Search className="h-4 w-4 text-muted" />
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search metrics…" className="w-full bg-transparent text-sm outline-none" />
        <button onClick={onClose} aria-label="Close"><X className="h-4 w-4 text-muted" /></button>
      </div>
      <div className="mt-2 max-h-80 overflow-auto">
        {groups.map(([g, ks]) => (
          <div key={g} className="mb-2">
            <div className="label px-2 py-1">{g}</div>
            {ks.map((k) => (
              <button key={k} onClick={() => onPick(k)} className="block w-full rounded-lg px-2 py-1.5 text-left hover:bg-white/5">
                <div className="text-sm text-white">{fields[k].label}</div>
                <div className="text-[11px] text-muted">{fields[k].description}</div>
              </button>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function Screener() {
  const router = useRouter();
  const params = useSearchParams();
  const [fields, setFields] = useState<Record<string, FieldInfo>>({});
  const [stats, setStats] = useState<Stats | null>(null);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [filters, setFilters] = useState<Filter[]>([]);
  const [sector, setSector] = useState<string>(params.get("sector") ?? "");
  const [mode, setMode] = useState<"builder" | "text">("builder");
  const [text, setText] = useState(params.get("q") ?? "market_cap > 1000 and roe > 15");
  const [picker, setPicker] = useState(false);
  const [sort, setSort] = useState({ field: "market_cap", order: "desc" as "asc" | "desc" });
  const [data, setData] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"table" | "scatter">("table");
  const [axes, setAxes] = useState<{ x: string; y: string } | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [copied, setCopied] = useState(false);
  const [ready, setReady] = useState(false);
  const textRef = useRef(text);
  textRef.current = text;

  // Load metadata, then turn the URL query into builder filters.
  useEffect(() => {
    Promise.all([
      api<Record<string, FieldInfo>>("/screener/fields"),
      api<Preset[]>("/screener/presets").catch(() => []),
      api<Stats>("/screener/stats").catch(() => null),
    ]).then(([f, p, s]) => {
      setFields(f);
      setPresets(p);
      setStats(s);
      const parsed = fromQuery(textRef.current, f);
      if (parsed) setFilters(parsed);
      else setMode("text");
      setReady(true);
    }).catch((e) => setError(e.message));
  }, []);

  const builderQuery = toQuery(filters);
  const query = mode === "builder" ? builderQuery : text;
  const inflight = useRef<AbortController | null>(null);

  const run = useCallback((q: string, s: { field: string; order: "asc" | "desc" }) => {
    inflight.current?.abort(); // drop out-of-order responses
    const ctrl = new AbortController();
    inflight.current = ctrl;
    setLoading(true);
    setError(null);
    api<Result>("/screener", {
      method: "POST", signal: ctrl.signal,
      body: JSON.stringify({ query: q, sector: sector || null, sort: s.field, order: s.order, limit: 300 }),
    })
      .then((d) => {
        setData(d);
        const qs = new URLSearchParams();
        if (q) qs.set("q", q);
        if (sector) qs.set("sector", sector);
        router.replace(`/screener?${qs.toString()}`, { scroll: false });
      })
      .catch((e) => { if (!ctrl.signal.aborted) setError(e.message); })
      .finally(() => { if (inflight.current === ctrl) setLoading(false); });
  }, [sector, router]);

  // Live results while editing the builder (debounced). Text mode runs on demand (button / Ctrl+Enter)
  // and when sort or sector change - never per keystroke.
  useEffect(() => {
    if (!ready) return;
    if (mode === "text") {
      run(textRef.current, sort);
      return;
    }
    const t = setTimeout(() => run(builderQuery, sort), 450);
    return () => clearTimeout(t);
  }, [ready, builderQuery, mode, run, sort]);

  const update = (id: number, patch: Partial<Filter>) => setFilters((fs) => fs.map((f) => (f.id === id ? { ...f, ...patch } : f)));
  const addFilter = (field: string) => {
    const d = stats?.fields[field];
    const hib = fields[field]?.higher_is_better;
    const value = d?.p50 !== undefined ? String(Number(d.p50.toPrecision(3))) : "0";
    setFilters((fs) => [...fs, { id: nextId++, field, op: hib === false ? "<" : ">", value }]);
    setPicker(false);
  };
  const applyPreset = (p: Preset) => {
    const parsed = fromQuery(p.query, fields);
    if (parsed) {
      setMode("builder");
      setFilters(parsed);
    } else {
      setMode("text");
      setText(p.query);
      run(p.query, sort);
    }
  };
  const switchMode = () => {
    if (mode === "builder") {
      setText(toQuery(filters));
      setMode("text");
      return;
    }
    const parsed = fromQuery(text, fields);
    if (parsed) {
      setFilters(parsed);
      setMode("builder");
    } else setError("This query can't be shown in the builder. Use simple conditions like 'roe > 15' joined with 'and'.");
  };
  const toggleSort = (field: string) => setSort((s) => ({ field, order: s.field === field && s.order === "desc" ? "asc" : "desc" }));
  const toggleSelect = (s: string) => setSelected((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : cur.length >= 5 ? cur : [...cur, s]));

  const filtered = Array.from(new Set(filters.map((f) => f.field)));
  const columns = Array.from(new Set([...filtered, ...CORE])).filter((c) => fields[c]).slice(0, 10);
  const english = filters
    .filter((f) => f.value !== "" && !isNaN(Number(f.value)) && fields[f.field])
    .map((f) => `${fields[f.field].label} ${OP_WORDS[f.op]} ${fmtField(Number(f.value), fields[f.field].unit).replace(/^\+/, "")}`);

  const summary = useMemo(() => {
    const rows = data?.results ?? [];
    const med = (k: string) => median(rows.map((r) => toNum(r[k as keyof Stock] as never)));
    const sectors = new Map<string, number>();
    rows.forEach((r) => r.sector && sectors.set(r.sector, (sectors.get(r.sector) ?? 0) + 1));
    return {
      items: ["roe", "pe", "return_1y", "dividend_yield"].map((k) => ({ k, v: med(k), mkt: stats?.fields[k]?.p50 ?? null })),
      sectors: Array.from(sectors.entries()).sort((a, b) => b[1] - a[1]).slice(0, 6),
    };
  }, [data, stats]);

  const scatterAxes = axes ?? { x: filtered[1] ?? "pe", y: filtered[0] ?? "roe" };
  const share = () => navigator.clipboard?.writeText(window.location.href).then(() => {
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  });

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Stock screener</h1>
          <p className="mt-1 text-sm text-muted">Add metrics to build a screen. Each one shows where the whole market sits, so you can see how strict your filter is.</p>
        </div>
        <button onClick={switchMode} className="btn text-xs"><Code2 className="h-3.5 w-3.5" /> {mode === "builder" ? "Type a query" : "Use the builder"}</button>
      </div>

      <div className="flex flex-wrap gap-2">
        {presets.map((p) => (
          <button key={p.id} title={p.description} className="chip" onClick={() => applyPreset(p)}>{p.name}</button>
        ))}
      </div>
      <SectionNote>Presets are example filters on public data, not stock picks or recommendations. Results change daily.</SectionNote>

      <div className="panel p-4">
        {mode === "builder" ? (
          <>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {filters.map((f) => {
                const meta = fields[f.field];
                const d = stats?.fields[f.field];
                const v = f.value === "" || isNaN(Number(f.value)) ? null : Number(f.value);
                const pass = v !== null ? passShare(d, f.op, v) : null;
                const hib = meta?.higher_is_better;
                return (
                  <div key={f.id} className="rounded-xl border border-white/[0.07] bg-black/25 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="text-sm font-medium text-white">{meta?.label ?? f.field}</div>
                        <div className="text-[11px] text-muted">{meta?.description}</div>
                      </div>
                      <button onClick={() => setFilters((fs) => fs.filter((x) => x.id !== f.id))} aria-label="Remove filter" className="text-muted hover:text-white"><X className="h-4 w-4" /></button>
                    </div>
                    <div className="mt-2 flex items-center gap-2">
                      <select value={f.op} onChange={(e) => update(f.id, { op: e.target.value as Op })} className="rounded-md border border-line bg-panel px-2 py-1 text-sm text-slate-200" aria-label="Condition">
                        {OPS.map((o) => <option key={o} value={o}>{OP_WORDS[o]}</option>)}
                      </select>
                      <input value={f.value} onChange={(e) => update(f.id, { value: e.target.value })} inputMode="decimal" className="num w-28 rounded-md border border-line bg-black/30 px-2 py-1 text-sm text-white outline-none focus:border-accent/60" aria-label={`${meta?.label ?? f.field} value`} />
                      <span className="text-xs text-muted">{meta?.unit}</span>
                    </div>
                    <Histogram d={d} op={f.op} value={v} />
                    <div className="mt-1 flex flex-wrap items-center justify-between gap-1 text-[11px] text-muted">
                      <span>{pass !== null ? <>≈<span className="num text-slate-200">{pass.toFixed(0)}%</span> of stocks pass</> : "No market data"}</span>
                      {d?.p25 !== undefined && d.p75 !== undefined && d.p10 !== undefined && d.p90 !== undefined && d.p50 !== undefined && hib !== null && hib !== undefined && (
                        <span className="flex gap-1">
                          {([["Top half", d.p50], ["Top 25%", hib ? d.p75 : d.p25], ["Top 10%", hib ? d.p90 : d.p10]] as [string, number][]).map(([label, val]) => (
                            <button key={label} onClick={() => update(f.id, { op: hib ? ">" : "<", value: String(Number(val.toPrecision(3))) })} className="rounded border border-line px-1.5 py-0.5 hover:text-white">{label}</button>
                          ))}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
              <div className="relative">
                <button onClick={() => setPicker((p) => !p)} className="flex h-full min-h-[120px] w-full flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-line text-sm text-muted hover:border-accent/60 hover:text-white">
                  <Plus className="h-5 w-5" /> Add a metric
                </button>
                {picker && <FieldPicker fields={fields} onPick={addFilter} onClose={() => setPicker(false)} />}
              </div>
            </div>
            {english.length > 0 && (
              <p className="mt-3 text-sm text-slate-300">
                <span className="text-muted">Showing companies with </span>
                {english.join(", ").replace(/, ([^,]*)$/, " and $1")}
                {sector ? <> in <span className="text-white">{sector}</span></> : ""}.
              </p>
            )}
          </>
        ) : (
          <>
            <textarea value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run(text, sort); }} rows={3} spellCheck={false} className="num w-full resize-y bg-transparent text-sm text-white outline-none" aria-label="Screener query" />
            <div className="mt-2 flex justify-end"><button className="btn-primary" onClick={() => run(text, sort)} disabled={loading}>Run screen</button></div>
          </>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3 text-xs">
          <span className="text-muted">Sector</span>
          <div className="relative">
            <select value={sector} onChange={(e) => setSector(e.target.value)} className="appearance-none rounded-md border border-line bg-panel py-1 pl-2 pr-7 text-slate-200" aria-label="Sector">
              <option value="">All sectors</option>
              {stats?.sectors.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1.5 h-3.5 w-3.5 text-muted" />
          </div>
        </div>
      </div>

      {error && <ErrorNote message={error} />}
      {!data && loading && <Loading />}

      {data && (
        <div className="panel overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
            <div className="text-sm">
              <span className="num text-lg font-semibold text-white">{data.total.toLocaleString("en-IN")}</span>
              <span className="text-muted"> of {data.universe.toLocaleString("en-IN")} stocks match ({((data.total / Math.max(1, data.universe)) * 100).toFixed(1)}%)</span>
              {data.total > data.count && <span className="text-muted"> · showing first {data.count}</span>}
              {loading && <span className="ml-2 text-muted">updating…</span>}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {selected.length >= 2 && (
                <Link href={`/compare?symbols=${selected.map(encodeURIComponent).join(",")}`} className="btn-primary text-xs"><GitCompare className="h-3.5 w-3.5" /> Compare {selected.length}</Link>
              )}
              {selected.length === 1 && <span className="text-xs text-muted">Select one more to compare</span>}
              <div className="seg">
                <button onClick={() => setView("table")} className={clsx("seg-btn inline-flex items-center gap-1", view === "table" && "seg-btn-active")}><Table2 className="h-3.5 w-3.5" /> Table</button>
                <button onClick={() => setView("scatter")} className={clsx("seg-btn inline-flex items-center gap-1", view === "scatter" && "seg-btn-active")}><ScatterChart className="h-3.5 w-3.5" /> Scatter</button>
              </div>
              <button onClick={share} className="btn text-xs">{copied ? <Check className="h-3.5 w-3.5 text-up" /> : <Link2 className="h-3.5 w-3.5" />} {copied ? "Copied" : "Share"}</button>
            </div>
          </div>

          {data.total > 0 && (
            <div className="space-y-2 border-b border-line px-4 py-3 text-xs">
              <div className="flex flex-wrap gap-x-5 gap-y-1">
                {summary.items.map(({ k, v, mkt }) => (
                  <span key={k} className="text-muted">
                    Median {fields[k]?.label ?? k} <span className="num text-white">{fmtField(v, fields[k]?.unit ?? "")}</span>
                    {mkt !== null && <span className="num"> (market {fmtField(mkt, fields[k]?.unit ?? "")})</span>}
                  </span>
                ))}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {summary.sectors.map(([name, n]) => (
                  <button key={name} onClick={() => setSector(name === sector ? "" : name)} title="Filter to this sector" className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-slate-300 hover:bg-white/10">{name} <span className="num text-muted">{n}</span></button>
                ))}
              </div>
            </div>
          )}

          {view === "scatter" ? (
            <div className="p-4"><ScreenerScatter rows={data.results} fields={fields} x={scatterAxes.x} y={scatterAxes.y} onAxes={(x, y) => setAxes({ x, y })} /></div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs text-muted">
                    <th className="w-8 px-3 py-2" title="Select up to 5 to compare"><span className="sr-only">Select</span></th>
                    <th className="px-2 py-2 font-medium">Company</th>
                    {columns.map((c) => (
                      <th key={c} onClick={() => toggleSort(c)} className={clsx("cursor-pointer whitespace-nowrap px-3 py-2 text-right font-medium hover:text-white", filtered.includes(c) && "text-accent")}>
                        <span className="inline-flex items-center gap-1">
                          {fields[c]?.label ?? c}
                          {sort.field === c && (sort.order === "desc" ? <ArrowDown className="h-3 w-3" /> : <ArrowUp className="h-3 w-3" />)}
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className={clsx(loading && "opacity-60")}>
                  {data.results.map((s) => (
                    <tr key={s.symbol} className="table-row">
                      <td className="px-3 py-2">
                        <input type="checkbox" checked={selected.includes(s.symbol)} onChange={() => toggleSelect(s.symbol)} disabled={!selected.includes(s.symbol) && selected.length >= 5} aria-label={`Select ${s.symbol} to compare`} className="accent-[#7c9cff]" />
                      </td>
                      <td className="px-2 py-2">
                        <Link href={`/stock/${encodeURIComponent(s.symbol)}`} className="font-medium text-white hover:text-accent">{s.symbol}</Link>
                        <div className="max-w-[200px] truncate text-xs text-muted">{s.name}</div>
                      </td>
                      {columns.map((c) => {
                        const v = s[c as keyof Stock] as string | number | null;
                        return (
                          <td key={c} className={clsx("num whitespace-nowrap px-3 py-2 text-right", SIGNED.includes(c) && changeClass(v), filtered.includes(c) && "bg-accent/[0.04]")}>
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
