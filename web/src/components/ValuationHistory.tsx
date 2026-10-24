"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { ChartLine } from "lucide-react";
import { SectionNote } from "./Legal";
import { Loading } from "./ui";
import { api } from "@/lib/api";
import { useInView } from "@/lib/useInView";

const SimpleLineChart = dynamic(() => import("./PriceChart").then((m) => m.SimpleLineChart), { ssr: false, loading: () => <Loading /> });

interface Series {
  current: number | null;
  min: number | null;
  median: number | null;
  max: number | null;
  percentile: number | null;
  since: string | null;
  years: number | null;
  loss_weeks: number;
  points: { time: string; value: number }[];
}

interface ValuationResponse {
  as_of: string;
  pe: Series | null;
  pb: Series | null;
}

type Metric = "pe" | "pb";

const LABEL: Record<Metric, string> = { pe: "P/E", pb: "P/B" };
const NOTE: Record<Metric, string> = {
  pe: "Computed by genScr from NSE prices and company filings; trailing 12-month EPS; historical description, not a valuation call.",
  pb: "Computed by genScr from NSE prices and company filings; latest reported total equity; historical description, not a valuation call.",
};

const mon = (d: string) => new Date(d).toLocaleDateString("en-IN", { month: "short", year: "numeric" });

/** One plain sentence placing the current multiple within its own range. Describes history only. */
function summary(label: string, s: Series): string {
  if (!s.points.length) {
    return `${label} is not meaningful: trailing earnings were negative in ${s.loss_weeks} weeks, so there is nothing to plot.`;
  }
  if (s.current === null || s.min === null || s.max === null || s.median === null || !s.since) {
    return `${label} is not available for today's date.`;
  }
  // Name the metric and the window so the figure reads as history, not a judgement on price.
  const where = s.percentile === 0
    ? `Today's ${label} is the lowest weekly reading since ${mon(s.since)}.`
    : `Today's ${label} is higher than ${s.percentile}% of weekly readings since ${mon(s.since)}.`;
  return `${label} now ${s.current.toFixed(1)}; since ${mon(s.since)} it ranged ${s.min.toFixed(1)}–${s.max.toFixed(1)} (median ${s.median.toFixed(1)}). ${where}`;
}

export default function ValuationHistory({ symbol }: { symbol: string }) {
  const { ref, inView } = useInView<HTMLDivElement>();
  const [d, setD] = useState<ValuationResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [metric, setMetric] = useState<Metric>("pe");

  useEffect(() => {
    if (!inView) return;
    api<ValuationResponse>(`/stocks/${encodeURIComponent(symbol)}/valuation`).then(setD).catch(() => setFailed(true));
  }, [inView, symbol]);

  // Fall back to the other multiple when the chosen one has no history (e.g. P/B for a stock with no usable P/E).
  const shown: Metric | null = !d
    ? null
    : metric === "pe" ? (d.pe ? "pe" : d.pb ? "pb" : null) : d.pb ? "pb" : d.pe ? "pe" : null;
  const s = shown && d ? d[shown] : null;
  const series = useMemo(() => s?.points ?? [], [s]);

  return (
    <div ref={ref}>
      {!d && !failed && inView && <Loading />}

      {d && shown && s && (
        <section className="panel p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <ChartLine className="h-5 w-5 text-accent" />
              <h2 className="text-lg font-semibold text-white">Valuation history</h2>
            </div>
            {d.pe && d.pb && (
              <div className="seg">
                {(["pe", "pb"] as const).map((m) => (
                  <button key={m} onClick={() => setMetric(m)} className={clsx("seg-btn", shown === m && "seg-btn-active")}>
                    {LABEL[m]}
                  </button>
                ))}
              </div>
            )}
          </div>

          <p className="mt-3 text-sm text-slate-200">{summary(LABEL[shown], s)}</p>

          {series.length > 0 && (
            <div className="mt-4">
              <SimpleLineChart series={series} median={s.median ?? undefined} />
            </div>
          )}

          <div className="mt-3 space-y-1.5">
            <SectionNote>{NOTE[shown]}</SectionNote>
            {s.years !== null && series.length > 0 && (
              <SectionNote>Weekly values for {s.years.toFixed(1)} years{s.loss_weeks > 0 ? `; P/E is not plotted for ${s.loss_weeks} weeks of negative trailing earnings` : ""}.</SectionNote>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
