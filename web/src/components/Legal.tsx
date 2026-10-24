"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangle, Info, X } from "lucide-react";
import { DISCLAIMER_SHORT, STALE_AFTER_DAYS } from "@/lib/site";

/** Small inline notice placed next to analytics (screener, compare, calculator, facts). */
export function SectionNote({ children }: { children: React.ReactNode }) {
  return (
    <p className="flex items-start gap-1.5 text-[11px] leading-relaxed text-muted">
      <Info className="mt-px h-3.5 w-3.5 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

/** Warns when the latest data is older than STALE_AFTER_DAYS. */
export function StaleDataBanner({ asOf }: { asOf: string | null | undefined }) {
  if (!asOf) return null;
  const days = Math.floor((Date.now() - new Date(asOf).getTime()) / 86_400_000);
  if (days <= STALE_AFTER_DAYS) return null;
  return (
    <div className="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-200">
      <AlertTriangle className="h-4 w-4 shrink-0" />
      Data was last updated on {new Date(asOf).toLocaleDateString("en-IN", { dateStyle: "medium" })} ({days} days ago) and may be outdated.
    </div>
  );
}

/** Non-blocking first-visit notice; remembered per browser. */
export function DisclaimerNotice() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    try {
      setShow(localStorage.getItem("disclaimer-ack") !== "1");
    } catch {
      setShow(true);
    }
  }, []);
  if (!show) return null;
  const dismiss = () => {
    try {
      localStorage.setItem("disclaimer-ack", "1");
    } catch {
      /* storage unavailable: just hide for this visit */
    }
    setShow(false);
  };
  return (
    <div role="note" className="fixed inset-x-0 bottom-0 z-50 border-t border-amber-500/30 bg-bg/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3 text-sm">
        <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
        <span className="text-xs text-slate-300 sm:text-sm">
          {DISCLAIMER_SHORT}<span className="hidden sm:inline"> Data may be delayed or inaccurate.</span>{" "}
          <Link href="/disclaimer" className="text-accent underline-offset-2 hover:underline">Disclaimer</Link>
        </span>
        <button onClick={dismiss} className="btn ml-auto shrink-0 text-xs" aria-label="Dismiss disclaimer notice">
          I understand <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
