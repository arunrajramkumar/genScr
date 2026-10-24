"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { Users } from "lucide-react";
import { SectionNote } from "./Legal";
import { LINE_COLORS } from "./chartColors";
import { api } from "@/lib/api";
import type { ShareholdingQuarter } from "@/lib/types";

const COLORS = { promoter: LINE_COLORS[0], fii: LINE_COLORS[1], dii: LINE_COLORS[2], other: "rgba(255,255,255,0.22)" };
const SUMMARY_QUARTERS = 4;

const monthYear = (d: string) => new Date(d).toLocaleDateString("en-IN", { month: "short", year: "numeric" });
const shortQuarter = (d: string) => {
  const dt = new Date(d);
  return `${dt.toLocaleDateString("en-IN", { month: "short" })}’${String(dt.getFullYear()).slice(2)}`;
};
const pct = (v: number | null) => (v === null ? "—" : `${v.toFixed(1)}%`);

// Bar segments in stacking order, bottom to top. Other public = public minus FII and DII; quarters without
// the FII/DII split show all of public as other public.
function segments(q: ShareholdingQuarter) {
  const promoter = q.promoter_pct ?? 0;
  if (q.fii_pct !== null && q.dii_pct !== null && q.public_pct !== null) {
    return { promoter, fii: q.fii_pct, dii: q.dii_pct, other: Math.max(0, q.public_pct - q.fii_pct - q.dii_pct) };
  }
  return { promoter, fii: 0, dii: 0, other: q.public_pct ?? Math.max(0, 100 - promoter) };
}

function summarize(rows: ShareholdingQuarter[]): string | null {
  const last = rows[rows.length - 1];
  if (last.promoter_pct === null) return null;
  if (last.promoter_pct === 0) {
    return `No promoter group is listed; the public holds ${last.public_pct?.toFixed(1) ?? "100"}% as of ${monthYear(last.period_end)}.`;
  }
  const now = last.promoter_pct.toFixed(1);
  const span = Math.min(SUMMARY_QUARTERS, rows.length - 1);
  const base = rows[rows.length - 1 - span].promoter_pct;
  if (span === 0 || base === null) return `Promoter holding ${now}% as of ${monthYear(last.period_end)}.`;
  const diff = Math.round((last.promoter_pct - base) * 10) / 10;
  const move = diff === 0 ? "unchanged" : `${diff > 0 ? "up" : "down"} ${Math.abs(diff).toFixed(1)} points`;
  return `Promoter holding ${now}%, ${move} over ${span} quarter${span === 1 ? "" : "s"}.`;
}

export default function Shareholding({ symbol }: { symbol: string }) {
  const [rows, setRows] = useState<ShareholdingQuarter[] | null>(null);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    api<ShareholdingQuarter[]>(`/stocks/${encodeURIComponent(symbol)}/shareholding`).then(setRows).catch(() => setRows([]));
  }, [symbol]);

  if (!rows || rows.length === 0) return null;

  const hasSplit = rows.some((r) => r.fii_pct !== null || r.dii_pct !== null);
  const summary = summarize(rows);
  const index = hover ?? rows.length - 1;
  const shown = rows[index];
  const shownSeg = segments(shown);

  return (
    <section className="panel p-5">
      <div className="flex items-center gap-2">
        <Users className="h-5 w-5 text-accent" />
        <h2 className="text-lg font-semibold text-white">Shareholding pattern</h2>
      </div>
      {summary && <p className="mt-2 text-sm text-slate-300">{summary}</p>}

      <div className="mt-4 flex h-44 items-end gap-1.5" onMouseLeave={() => setHover(null)}>
        {rows.map((r, i) => {
          const s = segments(r);
          return (
            <div
              key={r.period_end}
              className={clsx("flex h-full flex-1 cursor-default flex-col-reverse transition-opacity", hover !== null && hover !== i && "opacity-50")}
              onMouseEnter={() => setHover(i)}
              onClick={() => setHover(i)}
            >
              <div className="w-full overflow-hidden rounded-t" style={{ height: `${s.promoter}%`, backgroundColor: COLORS.promoter }} />
              <div className="w-full" style={{ height: `${s.fii}%`, backgroundColor: COLORS.fii }} />
              <div className="w-full" style={{ height: `${s.dii}%`, backgroundColor: COLORS.dii }} />
              <div className="w-full" style={{ height: `${s.other}%`, backgroundColor: COLORS.other }} />
            </div>
          );
        })}
      </div>
      <div className="mt-1 flex gap-1.5 text-[9px] text-muted">
        {rows.map((r) => (
          <span key={r.period_end} className="num flex-1 text-center">{shortQuarter(r.period_end)}</span>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        <span className="num text-slate-300">{monthYear(shown.period_end)}</span>
        <Key color={COLORS.promoter} label="Promoter" value={pct(shown.promoter_pct)} />
        {hasSplit && <Key color={COLORS.fii} label="FII" value={pct(shown.fii_pct)} />}
        {hasSplit && <Key color={COLORS.dii} label="DII" value={pct(shown.dii_pct)} />}
        {hasSplit && shown.mf_pct !== null && <span>of which MF <span className="num text-slate-200">{pct(shown.mf_pct)}</span></span>}
        <Key color={COLORS.other} label={hasSplit ? "Other public" : "Public"} value={`${shownSeg.other.toFixed(1)}%`} />
      </div>

      <div className="mt-3">
        <SectionNote>Source: NSE shareholding pattern filings for each quarter end (a revised filing replaces the original). Promoter includes the promoter group. FII and DII are shown where the filing gives the category split; MF is part of DII. Other public is public minus FII and DII. Changes in holdings are historical facts, not signals.</SectionNote>
      </div>
    </section>
  );
}

function Key({ color, label, value }: { color: string; label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: color }} />
      {label} <span className="num text-slate-200">{value}</span>
    </span>
  );
}
