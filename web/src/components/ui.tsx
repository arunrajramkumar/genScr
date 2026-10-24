"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { AlertTriangle, Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { toNum } from "@/lib/format";
import type { Num } from "@/lib/types";

export function Stat({ label, value, sub, className }: { label: string; value: ReactNode; sub?: ReactNode; className?: string }) {
  return (
    <div className={clsx("panel p-4", className)}>
      <div className="label">{label}</div>
      <div className="num mt-1 text-lg font-semibold text-white">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}
    </div>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-sm text-muted">
      <Loader2 className="h-4 w-4 animate-spin" /> {label}
    </div>
  );
}

/** Full-page loader that explains free-tier cold starts if loading takes more than a few seconds. */
export function PageLoading() {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 3500);
    return () => clearTimeout(t);
  }, []);
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3 text-center">
      <Loader2 className="h-8 w-8 animate-spin text-accent" />
      <div className="text-sm text-slate-300">Loading market data…</div>
      {slow && (
        <div className="max-w-sm text-xs text-muted">
          Waking up the data server. On free hosting it sleeps when idle, so the first visit can take up to a minute.
        </div>
      )}
    </div>
  );
}

export function ErrorNote({ message, hint }: { message: string; hint?: ReactNode }) {
  return (
    <div className="panel flex gap-3 border-amber-500/30 p-4 text-sm">
      <AlertTriangle className="h-5 w-5 shrink-0 text-amber-400" />
      <div>
        <div className="font-medium text-amber-200">{message}</div>
        {hint && <div className="mt-1 text-muted">{hint}</div>}
      </div>
    </div>
  );
}

/** Colour-coded badge for Piotroski (0-9) or Altman Z''. */
export function ScoreBadge({ kind, value }: { kind: "piotroski" | "altman"; value: Num | undefined }) {
  const n = toNum(value);
  if (n === null) return <span className="text-muted">—</span>;
  const [tone, text] =
    kind === "piotroski"
      ? n >= 7 ? ["up", "Strong"] : n >= 4 ? ["mid", "Average"] : ["down", "Weak"]
      : n > 2.6 ? ["up", "Safe"] : n >= 1.1 ? ["mid", "Grey zone"] : ["down", "Distress"];
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        tone === "up" && "bg-up/15 text-up",
        tone === "mid" && "bg-amber-400/15 text-amber-300",
        tone === "down" && "bg-down/15 text-down",
      )}
    >
      <span className="num">{kind === "piotroski" ? `${n}/9` : n.toFixed(2)}</span> · {text}
    </span>
  );
}

/** Position of the current price within its 52-week range. */
export function RangeBar({ low, high, value }: { low: Num | undefined; high: Num | undefined; value: Num | undefined }) {
  const l = toNum(low), h = toNum(high), v = toNum(value);
  if (l === null || h === null || v === null || h <= l) return null;
  const pct = Math.min(100, Math.max(0, ((v - l) / (h - l)) * 100));
  return (
    <div className="relative h-1.5 w-full rounded-full bg-gradient-to-r from-down/60 via-amber-400/60 to-up/60">
      <div className="absolute top-1/2 h-3.5 w-1.5 -translate-y-1/2 rounded-full bg-white shadow" style={{ left: `calc(${pct}% - 3px)` }} />
    </div>
  );
}

export function heatClass(v: Num | undefined): string {
  const n = toNum(v);
  if (n === null) return "bg-white/5";
  if (n >= 2) return "bg-up/60";
  if (n >= 1) return "bg-up/40";
  if (n > 0) return "bg-up/20";
  if (n <= -2) return "bg-down/60";
  if (n <= -1) return "bg-down/40";
  if (n < 0) return "bg-down/20";
  return "bg-white/10";
}
