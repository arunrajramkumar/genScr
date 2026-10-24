import { useCallback, useMemo, useSyncExternalStore } from "react";

/**
 * No-login watchlist, stored only in this browser (localStorage).
 * Every storage access is wrapped in try/catch: storage can be blocked or full (private mode, site data cleared).
 * In that case the list still works for the current tab, held in memory.
 */

export const WATCHLIST_MAX = 50;

const KEY = "genscr.watchlist.v1";
const EVENT = "genscr:watchlist-change"; // same-tab updates (the storage event only fires in other tabs)
const SYMBOL = /^[A-Z0-9&-]{1,20}$/; // same rule as the API

/** Set only while localStorage refuses writes; holds the JSON that could not be saved. */
let memoryRaw: string | null = null;

export function normalizeSymbols(input: Iterable<string>): string[] {
  const out: string[] = [];
  for (const raw of input) {
    const s = raw.trim().toUpperCase();
    if (SYMBOL.test(s) && !out.includes(s)) out.push(s);
    if (out.length >= WATCHLIST_MAX) break;
  }
  return out;
}

function parse(raw: string): string[] {
  try {
    const value: unknown = JSON.parse(raw);
    return Array.isArray(value) ? normalizeSymbols(value.filter((v): v is string => typeof v === "string")) : [];
  } catch {
    return [];
  }
}

function readRaw(): string {
  if (memoryRaw !== null) return memoryRaw;
  try {
    return window.localStorage.getItem(KEY) ?? "[]";
  } catch {
    return "[]";
  }
}

function writeList(list: string[]): void {
  const json = JSON.stringify(list);
  try {
    window.localStorage.setItem(KEY, json);
    memoryRaw = null;
  } catch {
    memoryRaw = json;
  }
  window.dispatchEvent(new CustomEvent(EVENT));
}

function readList(): string[] {
  return parse(readRaw());
}

/** Adds or removes one symbol. Returns false only when adding would exceed the cap. */
export function toggleSymbol(symbol: string): boolean {
  const [s] = normalizeSymbols([symbol]);
  if (!s) return false;
  const list = readList();
  if (list.includes(s)) {
    writeList(list.filter((x) => x !== s));
    return true;
  }
  if (list.length >= WATCHLIST_MAX) return false;
  writeList([...list, s]);
  return true;
}

/** Merges symbols into the list (cap applies). Returns how many were added. */
export function mergeSymbols(incoming: string[]): number {
  const list = readList();
  const next = normalizeSymbols([...list, ...incoming]);
  if (next.length !== list.length) writeList(next);
  return next.length - list.length;
}

function subscribe(onChange: () => void): () => void {
  const onStorage = (e: StorageEvent) => {
    if (e.key === KEY || e.key === null) onChange();
  };
  window.addEventListener("storage", onStorage);
  window.addEventListener(EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(EVENT, onChange);
  };
}

// Server render (static export) and hydration start from an empty list.
const getServerSnapshot = () => "[]";

/**
 * Current watchlist, kept in sync across components (custom event) and tabs (storage event).
 * `toggle` returns false when the list is full and the symbol could not be added.
 */
export function useWatchlist() {
  // The snapshot is the raw JSON string: strings compare by value, so no render loop.
  const raw = useSyncExternalStore(subscribe, readRaw, getServerSnapshot);
  const symbols = useMemo(() => parse(raw), [raw]);
  const set = useMemo(() => new Set(symbols), [symbols]);
  const has = useCallback((symbol: string) => set.has(symbol.trim().toUpperCase()), [set]);
  const toggle = useCallback((symbol: string) => toggleSymbol(symbol), []);
  return { symbols, has, toggle };
}
