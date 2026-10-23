import Link from "next/link";
import clsx from "clsx";
import { changeClass, fmtPct, fmtPrice, toNum } from "@/lib/format";
import type { Stock } from "@/lib/types";

/** Infinite scrolling ticker of market movers (pauses on hover). */
export default function TickerTape({ stocks }: { stocks: Stock[] }) {
  if (!stocks.length) return null;
  const items = [...stocks, ...stocks]; // duplicated for a seamless loop
  return (
    <div className="group relative overflow-hidden border-y border-white/[0.06] bg-black/40 py-2 [mask-image:linear-gradient(90deg,transparent,black_6%,black_94%,transparent)]">
      <div className="flex w-max animate-marquee gap-8 group-hover:[animation-play-state:paused]">
        {items.map((s, i) => (
          <Link key={`${s.symbol}-${i}`} href={`/stock/${encodeURIComponent(s.symbol)}`} className="flex items-center gap-2 whitespace-nowrap text-sm hover:opacity-80">
            <span className="font-semibold text-white">{s.symbol}</span>
            <span className="num text-slate-300">{fmtPrice(s.close)}</span>
            <span className={clsx("num text-xs", changeClass(s.change_pct))}>
              {(toNum(s.change_pct) ?? 0) >= 0 ? "▲" : "▼"} {fmtPct(s.change_pct)}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
