"use client";

import { useEffect, useRef } from "react";
import { ColorType, createChart, type IChartApi } from "lightweight-charts";
import type { Candle } from "@/lib/types";

const BASE_OPTIONS = {
  layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#8391a7", fontSize: 11 },
  grid: { vertLines: { color: "rgba(28,38,56,0.5)" }, horzLines: { color: "rgba(28,38,56,0.5)" } },
  rightPriceScale: { borderColor: "#1c2638" },
  timeScale: { borderColor: "#1c2638" },
  crosshair: { mode: 0 },
  autoSize: true,
};

export function PriceChart({ data }: { data: Candle[] }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart: IChartApi = createChart(ref.current, BASE_OPTIONS);
    const candles = chart.addCandlestickSeries({
      upColor: "#22c55e", downColor: "#ef4444", borderVisible: false,
      wickUpColor: "#22c55e", wickDownColor: "#ef4444",
    });
    const volume = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "" });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });

    candles.setData(data.map((d) => ({ time: d.time, open: d.open, high: d.high, low: d.low, close: d.close })));
    volume.setData(
      data.map((d) => ({
        time: d.time,
        value: d.volume,
        color: d.close >= d.open ? "rgba(34,197,94,0.35)" : "rgba(239,68,68,0.35)",
      })),
    );
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [data]);

  return <div ref={ref} className="h-[380px] w-full" />;
}

const LINE_COLORS = ["#7c9cff", "#22c55e", "#f59e0b", "#ec4899", "#06b6d4"];

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

export { LINE_COLORS };
