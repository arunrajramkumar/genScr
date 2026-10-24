"use client";

import clsx from "clsx";

const THUMB = 20; // px, matches .slider thumb size in globals.css

/** Range slider with a dot and a clickable label for every year, so it's clear where each stop is. */
export default function YearSlider({ value, max, onChange, min = 1 }: { value: number; max: number; onChange: (y: number) => void; min?: number }) {
  const years = Array.from({ length: Math.max(0, max - min + 1) }, (_, i) => min + i);
  const at = (y: number) => (max === min ? 0.5 : (y - min) / (max - min));
  const left = (y: number) => `calc(${THUMB / 2}px + (100% - ${THUMB}px) * ${at(y)})`;
  const step = years.length > 12 ? 2 : 1; // keep labels readable on long histories; every dot stays
  return (
    <div className="select-none">
      <div className="relative h-6">
        <div className="absolute inset-x-[10px] top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-line" />
        <div className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-gradient-to-r from-accent/50 to-accent"
          style={{ left: THUMB / 2, width: `calc((100% - ${THUMB}px) * ${at(value)})` }} />
        {years.map((y) => (
          <span key={y} aria-hidden
            className={clsx("absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 transition",
              y <= value ? "border-accent bg-accent" : "border-white/25 bg-bg")}
            style={{ left: left(y) }} />
        ))}
        <input type="range" min={min} max={max} step={1} value={Math.min(value, max)} onChange={(e) => onChange(Number(e.target.value))}
          className="slider slider-ticks absolute inset-0 h-6" aria-label="Years ago" aria-valuetext={`${value} year${value > 1 ? "s" : ""} ago`} />
      </div>
      <div className="relative mt-1 h-5">
        {years.map((y) => (y === value || y === max || (y - min) % step === 0) && (
          <button key={y} type="button" onClick={() => onChange(y)}
            className={clsx("num absolute -translate-x-1/2 rounded px-1 text-[11px] transition hover:text-white",
              y === value ? "font-semibold text-accent" : "text-muted")}
            style={{ left: left(y) }}>{y}Y</button>
        ))}
      </div>
    </div>
  );
}
