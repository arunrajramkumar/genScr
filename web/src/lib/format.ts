import type { Num } from "./types";

export function toNum(v: Num | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
const compact = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

export function fmtNum(v: Num | undefined, digits = 2): string {
  const n = toNum(v);
  return n === null ? "—" : n.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function fmtPrice(v: Num | undefined): string {
  const n = toNum(v);
  return n === null ? "—" : `₹${inr.format(n)}`;
}

export function fmtPct(v: Num | undefined, signed = true): string {
  const n = toNum(v);
  if (n === null) return "—";
  return `${signed && n > 0 ? "+" : ""}${n.toFixed(2)}%`;
}

/** Values already in ₹ crore. */
export function fmtCr(v: Num | undefined): string {
  const n = toNum(v);
  if (n === null) return "—";
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(2)} L Cr`;
  return `₹${compact.format(n)} Cr`;
}

export function fmtVolume(v: Num | undefined): string {
  const n = toNum(v);
  if (n === null) return "—";
  if (n >= 1e7) return `${(n / 1e7).toFixed(2)} Cr`;
  if (n >= 1e5) return `${(n / 1e5).toFixed(2)} L`;
  return compact.format(n);
}

export function changeClass(v: Num | undefined): string {
  const n = toNum(v);
  if (n === null || n === 0) return "text-muted";
  return n > 0 ? "text-up" : "text-down";
}

export function fmtField(v: Num | undefined, unit: string): string {
  if (unit === "₹ Cr") return fmtCr(v);
  if (unit === "₹") return fmtPrice(v);
  if (unit === "%") return fmtPct(v);
  if (unit === "/9") return toNum(v) === null ? "—" : `${toNum(v)}/9`;
  if (unit === "x") return toNum(v) === null ? "—" : `${fmtNum(v)}x`;
  return fmtNum(v, unit === "" ? 2 : 0);
}
