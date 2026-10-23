"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import clsx from "clsx";
import { Trophy } from "lucide-react";
import { CompareChart, LINE_COLORS } from "@/components/PriceChart";
import { ErrorNote, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtField, toNum } from "@/lib/format";
import type { CompareResponse } from "@/lib/types";

const ROWS = [
  "close", "market_cap", "pe", "pb", "dividend_yield", "roe", "roce", "debt_to_equity", "net_margin", "revenue_growth_yoy",
  "profit_growth_yoy", "piotroski_f", "altman_z", "return_1m", "return_1y", "pct_from_52w_high", "rsi_14",
];

function Compare() {
  const router = useRouter();
  const params = useSearchParams();
  const symbols = params.get("symbols") ?? "";
  const [input, setInput] = useState(symbols);
  const [data, setData] = useState<CompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setInput(symbols);
    if (symbols.split(",").filter(Boolean).length < 2) {
      setData(null);
      return;
    }
    setError(null);
    api<CompareResponse>(`/compare?symbols=${encodeURIComponent(symbols)}`).then(setData).catch((e) => setError(e.message));
  }, [symbols]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const cleaned = input.toUpperCase().split(/[\s,]+/).filter(Boolean).slice(0, 5).join(",");
    router.push(`/compare?symbols=${encodeURIComponent(cleaned)}`);
  };

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
        <p className="mt-1 text-sm text-muted">Enter 2 to 5 NSE symbols. The best value in each row is highlighted.</p>
      </div>
      <form onSubmit={submit} className="flex gap-2">
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="TCS, INFY, HCLTECH" className="panel num w-full max-w-lg px-4 py-2 text-sm outline-none focus:border-accent/70" />
        <button className="btn-primary">Compare</button>
      </form>

      {error && <ErrorNote message={error} />}
      {!data && !error && symbols && <Loading />}

      {data && (
        <>
          <div className="panel p-4">
            <div className="label mb-2">1-year performance (rebased to 100)</div>
            <div className="mb-2 flex flex-wrap gap-3 text-xs">
              {Object.keys(data.performance).map((s, i) => (
                <span key={s} className="inline-flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ background: LINE_COLORS[i % LINE_COLORS.length] }} /> {s}
                </span>
              ))}
            </div>
            <CompareChart series={data.performance} />
          </div>

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
                            {i === winner && <Trophy className="h-3 w-3" />}
                            {fmtField(s[field as keyof typeof s] as string | number | null, meta?.unit ?? "")}
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
