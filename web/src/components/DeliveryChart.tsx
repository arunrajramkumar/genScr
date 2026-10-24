"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ColorType, CrosshairMode, createChart } from "lightweight-charts";
import { api } from "@/lib/api";
import { fmtNum } from "@/lib/format";
import { SectionNote } from "./Legal";

type DeliveryPoint = { time: string; deliv_pct: number };

const BAR = "rgba(124,156,255,0.55)"; // one neutral colour for every day: no up/down reading
const AVG = "#f5b942";
const WINDOW = 20;

/** Trailing mean over `n` trading days, emitted once a full window exists. */
function rollingAverage(points: DeliveryPoint[], n: number): { time: string; value: number }[] {
  const out: { time: string; value: number }[] = [];
  let sum = 0;
  for (let i = 0; i < points.length; i++) {
    sum += points[i].deliv_pct;
    if (i >= n) sum -= points[i - n].deliv_pct;
    if (i >= n - 1) out.push({ time: points[i].time, value: sum / n });
  }
  return out;
}

/** Delivery % (share of traded quantity taken for delivery) per day, with its 20-day average. */
export default function DeliveryChart({ symbol }: { symbol: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [points, setPoints] = useState<DeliveryPoint[] | null>(null);

  useEffect(() => {
    let current = true;
    setPoints(null);
    api<DeliveryPoint[]>(`/stocks/${encodeURIComponent(symbol)}/delivery`)
      .then((d) => current && setPoints(d))
      .catch(() => current && setPoints([]));
    return () => {
      current = false;
    };
  }, [symbol]);

  const avg = useMemo(() => (points ? rollingAverage(points, WINDOW) : []), [points]);
  const latest = points?.length ? points[points.length - 1] : null;
  const latestAvg = avg.length ? avg[avg.length - 1].value : null;

  useEffect(() => {
    if (!ref.current || !points?.length) return;
    const chart = createChart(ref.current, {
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#7d8aa0", fontSize: 11, fontFamily: "var(--font-mono)" },
      grid: { vertLines: { color: "rgba(22,30,43,0.35)" }, horzLines: { color: "rgba(22,30,43,0.35)" } },
      rightPriceScale: { borderColor: "#161e2b" },
      timeScale: { borderColor: "#161e2b", rightOffset: 4 },
      crosshair: { mode: CrosshairMode.Normal },
      handleScale: { axisPressedMouseMove: false },
      autoSize: true,
    });
    chart.addHistogramSeries({
      color: BAR, priceLineVisible: false, lastValueVisible: false, base: 0,
      priceFormat: { type: "custom", formatter: (v: number) => `${v.toFixed(0)}%` },
    }).setData(points.map((p) => ({ time: p.time, value: p.deliv_pct })));
    chart.addLineSeries({
      color: AVG, lineWidth: 2, title: "20D avg", priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
    }).setData(avg);
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [points, avg]);

  return (
    <div className="panel p-5">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="text-sm font-semibold text-slate-200">Delivery %</h2>
        {latest && (
          <p className="num text-xs text-muted">
            Latest <span className="text-slate-200">{fmtNum(latest.deliv_pct, 1)}%</span> on{" "}
            {new Date(latest.time).toLocaleDateString("en-IN", { dateStyle: "medium", timeZone: "UTC" })}
            {latestAvg !== null && (
              <>
                {" "}· 20-day average <span className="text-slate-200">{fmtNum(latestAvg, 1)}%</span>
              </>
            )}
          </p>
        )}
      </div>

      {points === null && <p className="py-10 text-center text-sm text-muted">Loading delivery data…</p>}
      {points !== null && points.length === 0 && (
        <p className="py-10 text-center text-sm text-muted">Delivery % is not available for this stock yet.</p>
      )}
      {points && points.length > 0 && <div ref={ref} className="h-[220px] w-full sm:h-[260px]" />}

      <SectionNote>
        Source: NSE daily security-wise bhavdata (delivery quantity and percentage, EQ and BE series). Delivery % is a market
        statistic, not an indicator of future price.
      </SectionNote>
    </div>
  );
}
