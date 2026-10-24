"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import clsx from "clsx";
import dynamic from "next/dynamic";
import { Plus, X } from "lucide-react";
import SearchBox from "@/components/SearchBox";
import { LINE_COLORS } from "@/components/chartColors";
import { SectionNote } from "@/components/Legal";
import { ErrorNote, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtField, toNum } from "@/lib/format";
import type { CompareResponse, Stock } from "@/lib/types";

const CompareChart = dynamic(() => import("@/components/PriceChart").then((m) => m.CompareChart), { ssr: false, loading: () => <Loading /> });
const CompareInsights = dynamic(() => import("@/components/CompareInsights"), { ssr: false, loading: () => <Loading /> });

const ROWS = [
  "close", "market_cap", "pe", "pb", "dividend_yield", "roe", "roce", "debt_to_equity", "net_margin", "revenue_growth_yoy",
  "profit_growth_yoy", "piotroski_f", "altman_z", "return_1m", "return_1y", "pct_from_52w_high", "rsi_14",
];

const MAX = 5;
// Starting points for people who don't know where to begin.
const SETS: [string, string[]][] = [
  ["IT services", ["TCS", "INFY", "HCLTECH", "WIPRO"]],
  ["Private banks", ["HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK"]],
  ["FMCG", ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA"]],
  ["Two-wheelers", ["BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT", "TVSMOTOR"]],
  ["Paints", ["ASIANPAINT", "BERGEPAINT", "KANSAINER"]],
];

/** Pick stocks by name or symbol; chips show the selection, peers of the first pick are offered as one-click adds. */
function StockPicker({ picked, onChange }: { picked: string[]; onChange: (next: string[]) => void }) {
  const [peers, setPeers] = useState<Stock[]>([]);
  const first = picked[0];

  useEffect(() => {
    if (!first) return setPeers([]);
    api<Stock[]>(`/stocks/${encodeURIComponent(first)}/peers`).then(setPeers).catch(() => setPeers([]));
  }, [first]);

  const add = (symbols: string[]) => onChange([...new Set([...picked, ...symbols.map((x) => x.toUpperCase())])].slice(0, MAX));
  const full = picked.length >= MAX;
  const suggestions = peers.filter((p) => !picked.includes(p.symbol)).slice(0, 6);

  return (
    <div className="panel space-y-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        {picked.map((sym, i) => (
          <span key={sym} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-white/5 py-1 pl-3 pr-1 text-sm text-white">
            <span className="h-2 w-2 rounded-full" style={{ background: LINE_COLORS[i % LINE_COLORS.length] }} />
            {sym}
            <button onClick={() => onChange(picked.filter((x) => x !== sym))} aria-label={`Remove ${sym}`} className="rounded-full p-1 text-muted hover:bg-white/10 hover:text-white">
              <X className="h-3.5 w-3.5" />
            </button>
          </span>
        ))}
        <div className="min-w-[240px] flex-1">
          <SearchBox
            onPick={(st) => add([st.symbol])}
            onBulk={add}
            exclude={picked}
            disabled={full}
            autoFocus={picked.length === 0}
            placeholder={full ? `Up to ${MAX} stocks; remove one to add another` : picked.length ? "Add another company…" : "Type a company name, e.g. Tata, Infosys, HDFC…"}
          />
        </div>
      </div>

      {suggestions.length > 0 && !full && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-muted">Same sector as {first}:</span>
          {suggestions.map((p) => (
            <button key={p.symbol} onClick={() => add([p.symbol])} title={p.name} className="chip inline-flex items-center gap-1">
              <Plus className="h-3 w-3" />{p.symbol}
            </button>
          ))}
        </div>
      )}

      {picked.length === 0 && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-muted">Or start with a group:</span>
          {SETS.map(([label, syms]) => (
            <button key={label} onClick={() => onChange(syms)} title={syms.join(", ")} className="chip">{label}</button>
          ))}
        </div>
      )}
      {picked.length === 1 && <p className="text-xs text-muted">Add at least one more company to compare.</p>}
    </div>
  );
}

function Compare() {
  const router = useRouter();
  const params = useSearchParams();
  const symbols = params.get("symbols") ?? "";
  const picked = symbols.split(",").map((x) => x.trim().toUpperCase()).filter(Boolean);
  const [data, setData] = useState<CompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (symbols.split(",").filter(Boolean).length < 2) {
      setData(null);
      return;
    }
    setError(null);
    api<CompareResponse>(`/compare?symbols=${encodeURIComponent(symbols)}`).then(setData).catch((e) => setError(e.message));
  }, [symbols]);

  const setPicked = (next: string[]) => router.replace(next.length ? `/compare?symbols=${next.map(encodeURIComponent).join(",")}` : "/compare", { scroll: false });

  // Same stock order (and so the same colours) everywhere on the page.
  const orderedPerformance = data
    ? Object.fromEntries(data.stocks.filter((s) => data.performance[s.symbol]).map((s) => [s.symbol, data.performance[s.symbol]]))
    : null;

  /** Index of the best stock for a row, or -1 when the field has no direction. */
  const best = (field: string): number => {
    const dir = data?.fields[field]?.higher_is_better;
    if (dir === null || dir === undefined || !data) return -1;
    let idx = -1, bestVal = 0;
    data.stocks.forEach((s, i) => {
      const v = toNum(s[field as keyof typeof s] as string | number | null);
      if (v === null || (field === "pe" && v <= 0)) return;
      if (idx === -1 || (dir ? v > bestVal : v < bestVal)) { idx = i; bestVal = v; }
    });
    return idx;
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Compare stocks</h1>
        <p className="mt-1 text-sm text-muted">Search by company name and pick 2 to 5 stocks. The highest or lowest value of each metric is highlighted for reference.</p>
      </div>
      <StockPicker picked={picked} onChange={setPicked} />

      {error && <ErrorNote message={error} />}
      {!data && !error && picked.length >= 2 && <Loading />}

      {data && (
        <>
          <div className="panel p-4">
            <div className="label mb-2">1-year performance (rebased to 100)</div>
            <div className="mb-2 flex flex-wrap gap-3 text-xs">
              {orderedPerformance && Object.keys(orderedPerformance).map((s, i) => (
                <span key={s} className="inline-flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ background: LINE_COLORS[i % LINE_COLORS.length] }} /> {s}
                </span>
              ))}
            </div>
            <CompareChart series={orderedPerformance ?? {}} />
          </div>

          <CompareInsights stocks={data.stocks} />

          <SectionNote>Highlights mark the numerically higher/lower value only. They are not a ranking or a recommendation.</SectionNote>
          <div className="panel overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left">
                  <th className="px-4 py-3 text-xs font-medium text-muted">Metric</th>
                  {data.stocks.map((s) => (
                    <th key={s.symbol} className="px-4 py-3 text-right">
                      <Link href={`/stock/${encodeURIComponent(s.symbol)}`} className="font-semibold text-white hover:text-accent">{s.symbol}</Link>
                      <div className="max-w-[160px] truncate text-xs font-normal text-muted">{s.name}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ROWS.map((field) => {
                  const meta = data.fields[field];
                  const winner = best(field);
                  return (
                    <tr key={field} className="table-row">
                      <td className="px-4 py-2 text-muted">{meta?.label ?? field}</td>
                      {data.stocks.map((s, i) => (
                        <td key={s.symbol} className={clsx("num px-4 py-2 text-right", i === winner && "font-semibold text-up")}>
                          <span className="inline-flex items-center gap-1">
                            {i === winner && <span className="h-1.5 w-1.5 rounded-full bg-up" aria-hidden />}
                            {fmtField(s[field as keyof typeof s] as string | number | null, meta?.unit ?? "", field)}
                          </span>
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<Loading />}>
      <Compare />
    </Suspense>
  );
}
