"use client";

import clsx from "clsx";
import { Filter as FilterIcon } from "lucide-react";
import { fmtField } from "@/lib/format";

export interface Dist { count: number; p10?: number; p25?: number; p50?: number; p75?: number; p90?: number; hist_lo?: number; hist_hi?: number; hist?: number[] }
export interface FunnelStep { label: string; remaining: number }
export type Sizes = { large: number; mid: number; small: number; unknown: number };

const SECTOR_COLORS = ["#7c9cff", "#00d47e", "#f5b942", "#ec4899", "#06b6d4", "#a78bfa", "#64748b"];
const SIZE_META: [keyof Sizes, string, string][] = [
  ["large", "Large cap", "#7c9cff"], ["mid", "Mid cap", "#06b6d4"], ["small", "Small cap", "#a78bfa"], ["unknown", "No market cap", "#334155"],
];

/** Approximate share of the market below `v` (0-100), interpolated between the published percentiles. */
export function percentileOf(d: Dist | undefined, v: number | null): number | null {
  if (v === null || !d || d.p10 === undefined || d.p25 === undefined || d.p50 === undefined || d.p75 === undefined || d.p90 === undefined) return null;
  const pts: [number, number][] = [[d.hist_lo ?? d.p10, 2], [d.p10, 10], [d.p25, 25], [d.p50, 50], [d.p75, 75], [d.p90, 90], [d.hist_hi ?? d.p90, 98]];
  if (v <= pts[0][0]) return 1;
  if (v >= pts[pts.length - 1][0]) return 99;
  for (let i = 1; i < pts.length; i++) {
    const [x1, y1] = pts[i];
    const [x0, y0] = pts[i - 1];
    if (v <= x1) return x1 === x0 ? y1 : y0 + ((v - x0) / (x1 - x0)) * (y1 - y0);
  }
  return null;
}

/** Thin bar under a value: where it sits in the whole market for that metric (neutral colour: position, not a rating). */
export function MarketPosition({ pct }: { pct: number | null }) {
  if (pct === null) return null;
  return (
    <div className="ml-auto mt-1 h-1 w-16 overflow-hidden rounded-full bg-white/[0.06]" title={`Higher than about ${Math.round(pct)}% of stocks`}>
      <div className="h-full rounded-full bg-accent/60" style={{ width: `${Math.max(4, pct)}%` }} />
    </div>
  );
}

/** How many stocks remain after each condition; the step that removes the largest share is marked. */
export function Funnel({ universe, steps }: { universe: number; steps: FunnelStep[] }) {
  if (!steps.length) return null;
  let prev = universe;
  const drops = steps.map((s) => {
    const kept = prev ? s.remaining / prev : 1;
    prev = s.remaining;
    return kept;
  });
  const strictest = steps.length > 1 ? drops.indexOf(Math.min(...drops)) : -1;
  return (
    <div className="mt-3 rounded-xl border border-white/[0.06] bg-black/20 p-3">
      <div className="mb-2 flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-muted"><FilterIcon className="h-3 w-3" /> How each condition narrows the market</div>
      <ol className="space-y-1.5">
        <li className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 text-xs">
          <div className="relative h-6 overflow-hidden rounded-md bg-white/[0.04]">
            <div className="absolute inset-y-0 left-0 rounded-md bg-white/10" style={{ width: "100%" }} />
            <span className="absolute inset-0 flex items-center px-2 text-slate-300">All stocks with data</span>
          </div>
          <span className="num w-24 text-right text-slate-300">{universe.toLocaleString("en-IN")}</span>
        </li>
        {steps.map((s, i) => (
          <li key={i} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 text-xs">
            <div className="relative h-6 overflow-hidden rounded-md bg-white/[0.04]">
              <div className={clsx("absolute inset-y-0 left-0 rounded-md transition-all", i === steps.length - 1 ? "bg-accent/45" : "bg-accent/20")}
                style={{ width: `${Math.max(1, (s.remaining / Math.max(1, universe)) * 100)}%` }} />
              <span className="absolute inset-0 flex items-center gap-2 truncate px-2 text-slate-200">
                {s.label}
                {i === strictest && <span className="rounded bg-gold/15 px-1.5 text-[10px] text-gold">narrows the most</span>}
              </span>
            </div>
            <span className="num w-24 text-right">
              <span className="text-white">{s.remaining.toLocaleString("en-IN")}</span>
              <span className="text-muted"> ({Math.round(drops[i] * 100)}%)</span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Stacked({ parts, onPick, active }: { parts: { label: string; n: number; color: string }[]; onPick?: (label: string) => void; active?: string }) {
  const total = parts.reduce((a, p) => a + p.n, 0) || 1;
  return (
    <>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-white/[0.05]">
        {parts.filter((p) => p.n > 0).map((p) => (
          <div key={p.label} title={`${p.label}: ${p.n}`} style={{ width: `${(p.n / total) * 100}%`, background: p.color }} className="h-full border-r border-bg/60 last:border-0" />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
        {parts.filter((p) => p.n > 0).map((p) => {
          const body = <><span className="h-2 w-2 shrink-0 rounded-full" style={{ background: p.color }} />{p.label} <span className="num text-muted">{p.n}</span></>;
          return onPick ? (
            <button key={p.label} onClick={() => onPick(p.label)} title="Filter to this sector"
              className={clsx("inline-flex items-center gap-1.5 text-[11px] hover:text-white", active === p.label ? "text-white underline" : "text-slate-300")}>{body}</button>
          ) : <span key={p.label} className="inline-flex items-center gap-1.5 text-[11px] text-slate-300">{body}</span>;
        })}
      </div>
    </>
  );
}

export interface MedianItem { key: string; label: string; unit: string; value: number | null; market: number | null }

/** Matches vs the whole market: medians, company size and sector mix. Descriptive only. */
export function Glance({ medians, sizes, sectors, total, onSector, activeSector }: {
  medians: MedianItem[]; sizes?: Sizes; sectors: [string, number][]; total: number; onSector: (s: string) => void; activeSector: string;
}) {
  const top = sectors.slice(0, 6);
  const other = sectors.slice(6).reduce((a, [, n]) => a + n, 0);
  const sectorParts = [...top.map(([label, n], i) => ({ label, n, color: SECTOR_COLORS[i] })), ...(other ? [{ label: "Other", n: other, color: SECTOR_COLORS[6] }] : [])];
  return (
    <div className="grid gap-3 border-b border-line px-4 py-4 lg:grid-cols-[1.4fr_1fr_1fr]">
      <div>
        <div className="label mb-2">Median of matches vs market</div>
        <div className="grid grid-cols-2 gap-2">
          {medians.map((m) => {
            const max = Math.max(m.value ?? 0, m.market ?? 0) || 1;
            return (
              <div key={m.key} className="rounded-lg border border-white/[0.06] bg-black/20 px-3 py-2">
                <div className="truncate text-[11px] text-muted">{m.label}</div>
                <div className="num text-sm font-semibold text-white">{fmtField(m.value, m.unit, m.key)}</div>
                {(m.value ?? 0) >= 0 && (m.market ?? 0) >= 0 && (
                  <div className="mt-1.5 space-y-1" aria-hidden>
                    <div className="h-1 rounded-full bg-accent/70" style={{ width: `${((m.value ?? 0) / max) * 100}%` }} />
                    <div className="h-1 rounded-full bg-white/20" style={{ width: `${((m.market ?? 0) / max) * 100}%` }} />
                  </div>
                )}
                <div className="num mt-1 text-[10px] text-muted">market {fmtField(m.market, m.unit, m.key)}</div>
              </div>
            );
          })}
        </div>
      </div>
      <div>
        <div className="label mb-2">Company size <span className="normal-case tracking-normal text-muted">(by market-cap rank)</span></div>
        {sizes ? <Stacked parts={SIZE_META.map(([k, label, color]) => ({ label, n: sizes[k], color }))} /> : <p className="text-xs text-muted">—</p>}
        <p className="mt-2 text-[10px] leading-relaxed text-muted">Large = top 100, mid = 101–250, small = the rest, as in SEBI&apos;s mutual-fund categories.</p>
      </div>
      <div>
        <div className="label mb-2">Sector mix <span className="normal-case tracking-normal text-muted">({total.toLocaleString("en-IN")} matches)</span></div>
        <Stacked parts={sectorParts} onPick={(s) => s !== "Other" && onSector(s)} active={activeSector} />
      </div>
    </div>
  );
}
