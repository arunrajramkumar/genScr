"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { fmtField, toNum } from "@/lib/format";
import type { FieldMeta, Stock } from "@/lib/types";

const PALETTE = ["#7c9cff", "#00d47e", "#f5b942", "#ec4899", "#06b6d4", "#a78bfa", "#fb923c", "#84cc16"];
const W = 900, H = 440, PAD = { l: 56, r: 16, t: 16, b: 40 };

function quantile(v: number[], p: number) {
  const s = [...v].sort((a, b) => a - b);
  const i = (s.length - 1) * p, lo = Math.floor(i), hi = Math.ceil(i);
  return s[lo] + (s[hi] - s[lo]) * (i - lo);
}

export default function ScreenerScatter({ rows, fields, x, y, onAxes }: {
  rows: Stock[]; fields: Record<string, FieldMeta>; x: string; y: string; onAxes: (x: string, y: string) => void;
}) {
  const router = useRouter();
  const [hover, setHover] = useState<Stock | null>(null);
  const numeric = Object.keys(fields);

  const { pts, xs, ys, sectors } = useMemo(() => {
    const pts = rows
      .map((r) => ({ r, xv: toNum(r[x as keyof Stock] as never), yv: toNum(r[y as keyof Stock] as never), m: toNum(r.market_cap) }))
      .filter((p) => p.xv !== null && p.yv !== null) as { r: Stock; xv: number; yv: number; m: number | null }[];
    const clip = (vals: number[]) => (vals.length > 8 ? [quantile(vals, 0.02), quantile(vals, 0.98)] : [Math.min(...vals), Math.max(...vals)]);
    const [x0, x1] = pts.length ? clip(pts.map((p) => p.xv)) : [0, 1];
    const [y0, y1] = pts.length ? clip(pts.map((p) => p.yv)) : [0, 1];
    const counts = new Map<string, number>();
    pts.forEach((p) => p.r.sector && counts.set(p.r.sector, (counts.get(p.r.sector) ?? 0) + 1));
    const sectors = Array.from(counts.entries()).sort((a, b) => b[1] - a[1]).slice(0, PALETTE.length).map((e) => e[0]);
    return { pts, xs: [x0, x1 === x0 ? x0 + 1 : x1], ys: [y0, y1 === y0 ? y0 + 1 : y1], sectors };
  }, [rows, x, y]);

  const sx = (v: number) => PAD.l + ((Math.min(Math.max(v, xs[0]), xs[1]) - xs[0]) / (xs[1] - xs[0])) * (W - PAD.l - PAD.r);
  const sy = (v: number) => H - PAD.b - ((Math.min(Math.max(v, ys[0]), ys[1]) - ys[0]) / (ys[1] - ys[0])) * (H - PAD.t - PAD.b);
  const maxM = Math.max(1, ...pts.map((p) => p.m ?? 0));
  const radius = (m: number | null) => (m ? 3 + Math.sqrt(m / maxM) * 13 : 3.5);
  const color = (s: string | null) => (s && sectors.includes(s) ? PALETTE[sectors.indexOf(s)] : "#5b6578");
  const ticks = (a: number, b: number) => Array.from({ length: 5 }, (_, i) => a + ((b - a) * i) / 4);
  const unit = (f: string) => fields[f]?.unit ?? "";

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted">
        <span>Y axis</span>
        <select value={y} onChange={(e) => onAxes(x, e.target.value)} className="rounded-md border border-line bg-panel px-2 py-1 text-slate-200">
          {numeric.map((f) => <option key={f} value={f}>{fields[f].label}</option>)}
        </select>
        <span>vs X axis</span>
        <select value={x} onChange={(e) => onAxes(e.target.value, y)} className="rounded-md border border-line bg-panel px-2 py-1 text-slate-200">
          {numeric.map((f) => <option key={f} value={f}>{fields[f].label}</option>)}
        </select>
        <span className="ml-auto">{pts.length} plotted · bubble size = market cap · click to open</span>
      </div>

      <div className="relative">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Scatter plot of screener results">
          {ticks(ys[0], ys[1]).map((t) => (
            <g key={`y${t}`}>
              <line x1={PAD.l} x2={W - PAD.r} y1={sy(t)} y2={sy(t)} stroke="rgba(255,255,255,0.05)" />
              <text x={PAD.l - 6} y={sy(t)} fill="#7d8aa0" fontSize="10" textAnchor="end" dominantBaseline="middle">{fmtField(t, unit(y))}</text>
            </g>
          ))}
          {ticks(xs[0], xs[1]).map((t) => (
            <g key={`x${t}`}>
              <line y1={PAD.t} y2={H - PAD.b} x1={sx(t)} x2={sx(t)} stroke="rgba(255,255,255,0.05)" />
              <text y={H - PAD.b + 16} x={sx(t)} fill="#7d8aa0" fontSize="10" textAnchor="middle">{fmtField(t, unit(x))}</text>
            </g>
          ))}
          <text x={W / 2} y={H - 6} fill="#9aa6ba" fontSize="11" textAnchor="middle">{fields[x]?.label}</text>
          <text x={12} y={H / 2} fill="#9aa6ba" fontSize="11" textAnchor="middle" transform={`rotate(-90 12 ${H / 2})`}>{fields[y]?.label}</text>
          {[...pts].sort((a, b) => (b.m ?? 0) - (a.m ?? 0)).map((p) => (
            <circle
              key={p.r.symbol}
              cx={sx(p.xv)}
              cy={sy(p.yv)}
              r={radius(p.m)}
              fill={color(p.r.sector)}
              fillOpacity={hover?.symbol === p.r.symbol ? 0.95 : 0.55}
              stroke={hover?.symbol === p.r.symbol ? "#fff" : color(p.r.sector)}
              strokeWidth={hover?.symbol === p.r.symbol ? 2 : 1}
              className="cursor-pointer transition-[fill-opacity]"
              onMouseEnter={() => setHover(p.r)}
              onMouseLeave={() => setHover(null)}
              onClick={() => router.push(`/stock/${encodeURIComponent(p.r.symbol)}`)}
            />
          ))}
        </svg>
        {hover && (
          <div className="pointer-events-none absolute right-2 top-2 rounded-xl border border-line bg-panel/95 px-3 py-2 text-xs shadow-xl">
            <div className="font-semibold text-white">{hover.symbol}</div>
            <div className="max-w-[220px] truncate text-muted">{hover.name}</div>
            <div className="num mt-1 text-slate-200">{fields[x]?.label}: {fmtField(hover[x as keyof Stock] as never, unit(x), x)}</div>
            <div className="num text-slate-200">{fields[y]?.label}: {fmtField(hover[y as keyof Stock] as never, unit(y), y)}</div>
          </div>
        )}
      </div>
      <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-muted">
        {sectors.map((s, i) => (
          <span key={s} className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: PALETTE[i] }} />{s}</span>
        ))}
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[#5b6578]" />Other / unknown</span>
      </div>
      <p className="mt-1 text-[11px] text-muted">Axes are clipped to the 2nd–98th percentile of results so extreme values don&apos;t squash the chart.</p>
    </div>
  );
}
