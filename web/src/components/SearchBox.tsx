"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { api } from "@/lib/api";
import { changeClass, fmtPct, fmtPrice } from "@/lib/format";
import type { Stock } from "@/lib/types";

interface Props {
  large?: boolean;
  autoFocus?: boolean;
  placeholder?: string;
  /** Picker mode: called with the chosen stock instead of opening its page. */
  onPick?: (s: Stock) => void;
  /** Picker mode: Enter on pasted text like "TCS, INFY" hands over every symbol. */
  onBulk?: (symbols: string[]) => void;
  /** Symbols to leave out of the suggestions (e.g. already picked). */
  exclude?: string[];
  disabled?: boolean;
}

export default function SearchBox({ large = false, autoFocus = false, placeholder, onPick, onBulk, exclude, disabled }: Props) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Stock[]>([]);
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);

  // Press "/" anywhere to focus search.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (e.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    if (onPick) return; // the page's main search keeps the shortcut
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onPick]);

  useEffect(() => {
    const term = q.trim();
    if (onBulk && /[,\s]/.test(term)) {
      setResults([]); // a list is being typed or pasted; Enter adds it
      return;
    }
    if (!term) {
      setResults([]);
      return;
    }
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      api<Stock[]>(`/search?q=${encodeURIComponent(term)}`, { signal: ctrl.signal })
        .then((r) => {
          setResults(r);
          setActive(0);
          setOpen(true);
        })
        .catch(() => {});
    }, 150);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [q]);

  const shown = exclude?.length ? results.filter((r) => !exclude.includes(r.symbol)) : results;

  const go = (stock: Stock) => {
    setOpen(false);
    setQ("");
    if (onPick) {
      onPick(stock);
      inputRef.current?.focus(); // ready for the next one
      return;
    }
    inputRef.current?.blur();
    router.push(`/stock/${encodeURIComponent(stock.symbol)}`);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, shown.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter" && onBulk && /[,\s]/.test(q.trim())) {
      e.preventDefault();
      onBulk(q.toUpperCase().split(/[\s,]+/).filter(Boolean));
      setQ("");
    } else if (e.key === "Enter" && shown[active]) {
      e.preventDefault();
      go(shown[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="relative w-full">
      <div
        className={clsx(
          "flex items-center gap-3 rounded-xl border border-line bg-panel/90 transition focus-within:border-accent/70 focus-within:shadow-[0_0_0_4px_rgba(124,156,255,0.12)]",
          large ? "px-5 py-4" : "px-3 py-2",
        )}
      >
        <Search className={clsx("shrink-0 text-muted", large ? "h-5 w-5" : "h-4 w-4")} />
        <input
          ref={inputRef}
          autoFocus={autoFocus}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={onKeyDown}
          onFocus={() => shown.length && setOpen(true)}
          disabled={disabled}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          placeholder={placeholder ?? "Search stocks by name or symbol…"}
          className={clsx("w-full bg-transparent outline-none placeholder:text-muted", large ? "text-lg" : "text-sm")}
          aria-label={placeholder ?? "Search stocks"}
        />
        {!onPick && <kbd className="hidden rounded border border-line px-1.5 py-0.5 text-[10px] text-muted sm:block">/</kbd>}
      </div>

      {open && shown.length > 0 && (
        <ul className="panel absolute z-50 mt-2 max-h-96 w-full overflow-auto p-1 shadow-2xl">
          {shown.map((s, i) => (
            <li key={s.symbol}>
              <button
                onMouseDown={(e) => { e.preventDefault(); go(s); }}
                onMouseEnter={() => setActive(i)}
                className={clsx(
                  "flex w-full items-center justify-between gap-4 rounded-lg px-3 py-2 text-left",
                  i === active && "bg-white/5",
                )}
              >
                <div className="min-w-0">
                  <div className="font-semibold text-white">{s.symbol}</div>
                  <div className="truncate text-xs text-muted">{s.name}</div>
                </div>
                <div className="text-right">
                  <div className="num text-sm">{fmtPrice(s.close)}</div>
                  <div className={clsx("num text-xs", changeClass(s.change_pct))}>{fmtPct(s.change_pct)}</div>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
