"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { ColorType, CrosshairMode, createChart, type IChartApi, type Time } from "lightweight-charts";
import { changeClass, fmtPct, fmtPrice, fmtVolume } from "@/lib/format";
import { movingAverage } from "@/lib/returns";
import { LINE_COLORS } from "./chartColors";
import type { Candle } from "@/lib/types";

const UP = "#00d47e";
const DOWN = "#ff4d5e";

const BASE_OPTIONS = {
  layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#7d8aa0", fontSize: 11, fontFamily: "var(--font-mono)" },
  grid: { vertLines: { color: "rgba(22,30,43,0.35)" }, horzLines: { color: "rgba(22,30,43,0.35)" } },
  rightPriceScale: { borderColor: "#161e2b" },
  timeScale: { borderColor: "#161e2b", rightOffset: 4 },
  crosshair: {
    mode: CrosshairMode.Normal,
    vertLine: { color: "rgba(124,156,255,0.4)", labelBackgroundColor: "#1c2638" },
    horzLine: { color: "rgba(124,156,255,0.4)", labelBackgroundColor: "#1c2638" },
  },
  handleScale: { axisPressedMouseMove: false },
  autoSize: true,
};

const RANGES = [
  { id: "1M", days: 31 }, { id: "6M", days: 183 }, { id: "1Y", days: 366 },
  { id: "3Y", days: 1097 }, { id: "5Y", days: 1827 }, { id: "MAX", days: Infinity },
] as const;

type RangeId = (typeof RANGES)[number]["id"];

export function StockChart({ data }: { data: Candle[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const [range, setRange] = useState<RangeId>("1Y");
  const [mode, setMode] = useState<"area" | "candle">("area");
  const [showMA, setShowMA] = useState(true);
  const [hover, setHover] = useState<Candle | null>(null);

  const visible = useMemo(() => {
    if (!data.length) return [];
    const days = RANGES.find((r) => r.id === range)!.days;
    if (!Number.isFinite(days)) return data;
    const cutoff = new Date(data[data.length - 1].time).getTime() - days * 86_400_000;
    return data.filter((d) => new Date(d.time).getTime() >= cutoff);
  }, [data, range]);

  const first = visible[0], last = visible[visible.length - 1];
  const rangeReturn = first && last && first.close ? (last.close / first.close - 1) * 100 : null;
  const positive = (rangeReturn ?? 0) >= 0;

  useEffect(() => {
    if (!ref.current || !visible.length) return;
    const chart: IChartApi = createChart(ref.current, BASE_OPTIONS);
    const color = positive ? UP : DOWN;

    const main =
      mode === "area"
        ? chart.addAreaSeries({
            lineColor: color, lineWidth: 2,
            topColor: positive ? "rgba(0,212,126,0.28)" : "rgba(255,77,94,0.28)",
            bottomColor: "rgba(0,0,0,0)",
            priceLineColor: color, crosshairMarkerBackgroundColor: color,
          })
        : chart.addCandlestickSeries({ upColor: UP, downColor: DOWN, borderVisible: false, wickUpColor: UP, wickDownColor: DOWN });
    if (mode === "area") main.setData(visible.map((d) => ({ time: d.time, value: d.close })));
    else main.setData(visible.map((d) => ({ time: d.time, open: d.open, high: d.high, low: d.low, close: d.close })));

    const volume = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "", lastValueVisible: false, priceLineVisible: false });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.84, bottom: 0 } });
    volume.setData(visible.map((d) => ({ time: d.time, value: d.volume, color: d.close >= d.open ? "rgba(0,212,126,0.25)" : "rgba(255,77,94,0.25)" })));

    if (showMA) {
      const start = visible[0].time;
      for (const [n, c] of [[50, "#f5b942"], [200, "#7c9cff"]] as const) {
        const ma = movingAverage(data, n).filter((p) => p.time >= start);
        if (ma.length) chart.addLineSeries({ color: c, lineWidth: 1, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false }).setData(ma);
      }
    }

    const byTime = new Map(visible.map((d) => [d.time, d]));
    chart.subscribeCrosshairMove((p) => {
      const t = p.time as Time | undefined;
      setHover(t ? byTime.get(String(t)) ?? null : null);
    });
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [visible, data, mode, showMA, positive]);

  const shown = hover ?? last;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="seg">
            {RANGES.map((r) => (
              <button key={r.id} onClick={() => setRange(r.id)} className={clsx("seg-btn", r.id === range && "seg-btn-active")}>{r.id}</button>
            ))}
          </div>
          {rangeReturn !== null && (
            <span className={clsx("num rounded-md px-2 py-1 text-xs font-semibold", positive ? "bg-up/10 text-up" : "bg-down/10 text-down")}>
              {range} {fmtPct(rangeReturn)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowMA((v) => !v)} className={clsx("seg-btn border border-line", showMA && "seg-btn-active")}>
            <span className="text-gold">50</span>/<span className="text-accent">200</span> DMA
          </button>
          <div className="seg">
            <button onClick={() => setMode("area")} className={clsx("seg-btn", mode === "area" && "seg-btn-active")}>Area</button>
            <button onClick={() => setMode("candle")} className={clsx("seg-btn", mode === "candle" && "seg-btn-active")}>Candles</button>
          </div>
        </div>
      </div>

      {shown && (
        <div className="num mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
          <span className="text-slate-300">{new Date(shown.time).toLocaleDateString("en-IN", { dateStyle: "medium" })}</span>
          <span>O <span className="text-slate-200">{fmtPrice(shown.open)}</span></span>
          <span>H <span className="text-slate-200">{fmtPrice(shown.high)}</span></span>
          <span>L <span className="text-slate-200">{fmtPrice(shown.low)}</span></span>
          <span>C <span className={changeClass(shown.close - shown.open)}>{fmtPrice(shown.close)}</span></span>
          <span>Vol <span className="text-slate-200">{fmtVolume(shown.volume)}</span></span>
        </div>
      )}
      <div ref={ref} className="h-[400px] w-full" />
    </div>
  );
}

export function CompareChart({ series }: { series: Record<string, { time: string; value: number }[]> }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, BASE_OPTIONS);
    Object.entries(series).forEach(([symbol, pts], i) => {
      const line = chart.addLineSeries({ color: LINE_COLORS[i % LINE_COLORS.length], lineWidth: 2, title: symbol });
      line.setData(pts.map((p) => ({ time: p.time, value: p.value })));
    });
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [series]);

  return <div ref={ref} className="h-[320px] w-full" />;
}

/** Invested vs current value over time, for the returns calculator. */
export function GrowthChart({ series, positive }: { series: { time: string; invested: number; value: number }[]; positive: boolean }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !series.length) return;
    const chart = createChart(ref.current, { ...BASE_OPTIONS, handleScroll: false, handleScale: false });
    const color = positive ? UP : DOWN;
    chart.addAreaSeries({
      lineColor: color, lineWidth: 2, topColor: positive ? "rgba(0,212,126,0.25)" : "rgba(255,77,94,0.25)", bottomColor: "rgba(0,0,0,0)",
      priceLineVisible: false, title: "Value",
    }).setData(series.map((p) => ({ time: p.time, value: Math.round(p.value) })));
    chart.addLineSeries({ color: "#7d8aa0", lineWidth: 1, lineStyle: 2, priceLineVisible: false, title: "Invested" })
      .setData(series.map((p) => ({ time: p.time, value: Math.round(p.invested) })));
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [series, positive]);

  return <div ref={ref} className="h-[260px] w-full" />;
}
