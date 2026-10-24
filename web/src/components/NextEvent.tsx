"use client";

import { useEffect, useState } from "react";
import { CalendarClock } from "lucide-react";
import { api } from "@/lib/api";
import type { EventsResponse } from "@/lib/types";

// One request per symbol, shared by every mount of this component. The list changes once a day.
const requests = new Map<string, Promise<EventsResponse>>();

function eventsFor(symbol: string): Promise<EventsResponse> {
  let req = requests.get(symbol);
  if (!req) {
    req = api<EventsResponse>(`/calendar/events?symbol=${encodeURIComponent(symbol)}`);
    req.catch(() => requests.delete(symbol)); // a later mount may retry after a failure
    requests.set(symbol, req);
  }
  return req;
}

const fmtDay = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { dateStyle: "medium" });

/** Next announced board meeting that covers financial results. Renders nothing when there is none. */
export default function NextEvent({ symbol }: { symbol: string }) {
  const [next, setNext] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    setNext(null);
    eventsFor(symbol)
      .then((d) => {
        const row = d.upcoming.find((e) => e.category === "results"); // upcoming is sorted by date
        if (current) setNext(row?.event_date ?? null);
      })
      .catch(() => {});
    return () => {
      current = false;
    };
  }, [symbol]);

  if (!next) return null;
  return (
    <p className="flex items-center gap-2 text-sm text-slate-300">
      <CalendarClock className="h-4 w-4 shrink-0 text-accent" aria-hidden />
      <span>Board meeting: {fmtDay(next)} · Financial results</span>
    </p>
  );
}
