"use client";

/** Where today's P/E sits within the index's own history, as a small bar. */
function ordinal(n: number): string {
  const r = n % 100;
  return `${n}${r >= 11 && r <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] ?? "th"}`;
}

export function ValuationBar({ pct }: { pct: number | null }) {
  if (pct === null) return <span className="text-muted">—</span>;
  return (
    <span className="inline-flex items-center gap-2" title={`Current P/E is higher than ${pct.toFixed(0)}% of trading days since the data starts`}>
      <span className="relative h-1.5 w-16 rounded-full bg-gradient-to-r from-slate-600 via-slate-500 to-slate-300">
        <span className="absolute top-1/2 h-3 w-1 -translate-y-1/2 rounded bg-gold" style={{ left: `calc(${pct}% - 2px)` }} />
      </span>
      <span className="num text-xs text-slate-300">{ordinal(Math.round(pct))}</span>
    </span>
  );
}

