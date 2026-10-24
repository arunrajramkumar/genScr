"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { SectionNote } from "@/components/Legal";
import { ErrorNote, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtCr, fmtPct } from "@/lib/format";

type Period = "1d" | "1m" | "1y";
interface HeatStock { symbol: string; name: string; market_cap: number; value: number }
interface HeatSector { sector: string; market_cap: number; stocks: HeatStock[] }
interface Heatmap { as_of: string | null; universe: string; period: Period; count: number; sectors: HeatSector[] }
interface Box { x: number; y: number; w: number; h: number }

const UNIVERSES: [string, string][] = [["all", "All stocks"], ["Nifty 50", "Nifty 50"], ["Nifty 500", "Nifty 500"]];
// [period, label, colour scale: colours clamp at +/- this many percent]
const PERIODS: [Period, string, number][] = [["1d", "1D", 5], ["1m", "1M", 15], ["1y", "1Y", 50]];
// Mirrors tailwind `up` / `down` (tailwind.config) and a neutral slate for zero change.
const UP = [0, 212, 126];
const DOWN = [255, 77, 94];
const NEUTRAL = [44, 50, 62];
const GAP = 1;
const HEADER = 18;

function tileColor(v: number, scale: number): string {
  const t = Math.max(-1, Math.min(1, v / scale));
  const target = t >= 0 ? UP : DOWN;
  const c = NEUTRAL.map((n, i) => Math.round(n + (target[i] - n) * Math.abs(t)));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

type Entry<T> = { item: T; size: number };
type Placed<T> = Box & { item: T };

/** Squarified treemap (Bruls et al.): lays out items by size inside `box`, keeping tiles close to square. */
function squarify<T>(entries: Entry<T>[], box: Box): Placed<T>[] {
  const total = entries.reduce((s, e) => s + e.size, 0);
  const k = total > 0 ? (box.w * box.h) / total : 0;
  const rest = [...entries].sort((a, b) => b.size - a.size).map((e) => ({ item: e.item, area: e.size * k }));
  const out: Placed<T>[] = [];
  let r = { ...box };
  while (rest.length) {
    const side = Math.min(r.w, r.h);
    const row = [rest.shift()!];
    while (rest.length && worst([...row, rest[0]], side) <= worst(row, side)) row.push(rest.shift()!);
    const area = row.reduce((s, e) => s + e.area, 0);
    const horizontal = r.w >= r.h; // the row runs along the shorter side
    const thick = area / side;
    let pos = horizontal ? r.y : r.x;
    for (const e of row) {
      const span = e.area / thick;
      out.push(horizontal
        ? { item: e.item, x: r.x, y: pos, w: thick, h: span }
        : { item: e.item, x: pos, y: r.y, w: span, h: thick });
      pos += span;
    }
    r = horizontal ? { x: r.x + thick, y: r.y, w: r.w - thick, h: r.h } : { x: r.x, y: r.y + thick, w: r.w, h: r.h - thick };
  }
  return out;
}

function worst(row: { area: number }[], side: number): number {
  const s = row.reduce((a, e) => a + e.area, 0);
  const max = Math.max(...row.map((e) => e.area));
  const min = Math.min(...row.map((e) => e.area));
  return Math.max((side * side * max) / (s * s), (s * s) / (side * side * min));
}

export default function MarketHeatmap() {
  const [universe, setUniverse] = useState("all");
  const [period, setPeriod] = useState<Period>("1d");
  const [data, setData] = useState<Heatmap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [width, setWidth] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    setWidth(Math.floor(el.clientWidth));  // don't wait for the first observer callback
    const ro = new ResizeObserver(([e]) => setWidth(Math.floor(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    let live = true;
    setError(null);
    api<Heatmap>(`/market/heatmap?universe=${encodeURIComponent(universe)}&period=${period}`)
      .then((d) => live && setData(d))
      .catch((e) => live && setError(e.message));
    return () => { live = false; };
  }, [universe, period]);

  const scale = PERIODS.find(([p]) => p === period)?.[2] ?? 5;
  const label = PERIODS.find(([p]) => p === period)?.[1] ?? "";
  const mobile = width > 0 && width < 640;
  const height = mobile ? 360 : 520;
  const sectorBoxes = data && width > 0 ? squarify(data.sectors.map((s) => ({ item: s, size: s.market_cap })), { x: 0, y: 0, w: width, h: height }) : [];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <div className="seg">
            {UNIVERSES.map(([v, l]) => (
              <button key={v} type="button" onClick={() => setUniverse(v)} className={clsx("seg-btn", universe === v && "seg-btn-active")}>{l}</button>
            ))}
          </div>
          <div className="seg">
            {PERIODS.map(([v, l]) => (
              <button key={v} type="button" onClick={() => setPeriod(v)} className={clsx("seg-btn", period === v && "seg-btn-active")}>{l}</button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted">
          <span className="num">-{scale}%</span>
          <div className="h-2 w-24 rounded-full" style={{ background: `linear-gradient(to right, ${tileColor(-scale, scale)}, ${tileColor(0, scale)}, ${tileColor(scale, scale)})` }} />
          <span className="num">+{scale}%</span>
        </div>
      </div>

      {error && <ErrorNote message={`Couldn't load the heatmap: ${error}`} />}

      <div ref={boxRef} className="relative w-full overflow-hidden rounded-xl bg-black/40" style={{ height }}>
        {!data && !error && <div className="absolute inset-0 flex items-center justify-center"><Loading label="Loading heatmap…" /></div>}
        {sectorBoxes.map(({ item: sec, x, y, w, h }) => {
          const showHead = h >= HEADER + 24 && w >= 72;
          const headH = showHead ? HEADER : 0;
          const tiles = squarify(sec.stocks.map((s) => ({ item: s, size: s.market_cap })), { x: 0, y: headH, w, h: h - headH });
          return (
            <div key={sec.sector} className="absolute" style={{ left: x, top: y, width: w, height: h }}>
              {showHead && (
                <div className="truncate px-1 text-[11px] font-semibold leading-[18px] text-slate-300" style={{ height: HEADER }}>{sec.sector}</div>
              )}
              {tiles.map(({ item: s, x: tx, y: ty, w: tw, h: th }) => {
                const showSym = tw >= 40 && th >= 26;
                const showPct = tw >= 48 && th >= 40;
                const tip = `${s.symbol} · ${s.name}\n${sec.sector}\nMarket cap ${fmtCr(s.market_cap)}\n${label === "1D" ? "Price change" : "Return"} (${label}): ${fmtPct(s.value)}`;
                return (
                  <Link
                    key={s.symbol}
                    href={`/stock/${encodeURIComponent(s.symbol)}`}
                    title={tip}
                    aria-label={tip.replace(/\n/g, ", ")}
                    className="absolute overflow-hidden rounded-[3px] p-1 text-white transition hover:z-10 hover:ring-1 hover:ring-white/80"
                    style={{
                      left: tx + GAP / 2, top: ty + GAP / 2, width: Math.max(0, tw - GAP), height: Math.max(0, th - GAP),
                      background: tileColor(s.value, scale), textShadow: "0 1px 2px rgba(0,0,0,0.45)",
                    }}
                  >
                    {showSym && <div className={clsx("truncate font-semibold leading-tight", mobile ? "text-[10px]" : "text-xs")}>{s.symbol}</div>}
                    {showPct && <div className={clsx("num leading-tight text-white/90", mobile ? "text-[10px]" : "text-[11px]")}>{fmtPct(s.value)}</div>}
                  </Link>
                );
              })}
            </div>
          );
        })}
      </div>

      {data && (
        <SectionNote>
          {period === "1d" ? "Price change" : "Return"} by sector, sized by market cap. {data.count} stocks
          {data.as_of ? ` as of ${new Date(data.as_of).toLocaleDateString("en-IN", { dateStyle: "medium" })}` : ""}. Colour clamps at
          ±{scale}%. Source: NSE bhavcopy (daily close). Stocks without market cap data are not shown. For information only, not a recommendation.
        </SectionNote>
      )}
    </div>
  );
}
