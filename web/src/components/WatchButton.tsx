"use client";

import clsx from "clsx";
import { Star } from "lucide-react";
import { WATCHLIST_MAX, useWatchlist } from "@/lib/watchlist";

export function WatchButton({ symbol }: { symbol: string }) {
  const { symbols, has, toggle } = useWatchlist();
  const code = symbol.trim().toUpperCase();
  const on = has(code);
  const full = !on && symbols.length >= WATCHLIST_MAX;
  const label = on ? "Remove from watchlist" : "Add to watchlist";

  return (
    <button
      type="button"
      onClick={() => toggle(code)}
      disabled={full}
      title={full ? `Your watchlist is full (${WATCHLIST_MAX} stocks). Remove one to add another.` : label}
      className={clsx("btn text-xs", on && "border-accent/60 text-accent")}
    >
      <Star className={clsx("h-3.5 w-3.5", on && "fill-current")} aria-hidden="true" />
      {label}
    </button>
  );
}
