"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import {
  ArrowDownToLine, Building2, Coins, Flag, Gift, GitBranch, History, Mountain, Play, Repeat, Scissors, Ticket,
  type LucideIcon,
} from "lucide-react";
import { SectionNote } from "./Legal";
import { Loading } from "./ui";
import { api } from "@/lib/api";
import { useInView } from "@/lib/useInView";
import type { TimelineEvent } from "@/lib/types";

const STYLE: Record<TimelineEvent["kind"], { icon: LucideIcon; color: string }> = {
  listing: { icon: Building2, color: "text-accent border-accent/40 bg-accent/10" },
  milestone: { icon: Flag, color: "text-accent border-accent/40 bg-accent/10" },
  dividend: { icon: Coins, color: "text-gold border-gold/40 bg-gold/10" },
  bonus: { icon: Gift, color: "text-up border-up/40 bg-up/10" },
  split: { icon: Scissors, color: "text-up border-up/40 bg-up/10" },
  rights: { icon: Ticket, color: "text-sky-300 border-sky-400/40 bg-sky-400/10" },
  buyback: { icon: Repeat, color: "text-sky-300 border-sky-400/40 bg-sky-400/10" },
  demerger: { icon: GitBranch, color: "text-pink-300 border-pink-400/40 bg-pink-400/10" },
  high: { icon: Mountain, color: "text-up border-up/40 bg-up/10" },
  drawdown: { icon: ArrowDownToLine, color: "text-down border-down/40 bg-down/10" },
};

const FILTERS: { id: string; label: string; kinds: TimelineEvent["kind"][] | null }[] = [
  { id: "all", label: "All", kinds: null },
  { id: "capital", label: "Bonus, splits & more", kinds: ["bonus", "split", "rights", "buyback", "demerger"] },
  { id: "dividend", label: "Dividends", kinds: ["dividend", "milestone"] },
  { id: "price", label: "Price milestones", kinds: ["high", "drawdown", "listing"] },
];

export default function CompanyTimeline({ symbol }: { symbol: string }) {
  const { ref, inView } = useInView<HTMLElement>();
  const [events, setEvents] = useState<TimelineEvent[] | null>(null);
  const [filter, setFilter] = useState("all");
  const [revealed, setRevealed] = useState(0);
  const listRef = useRef<HTMLOListElement>(null);

  useEffect(() => {
    if (!inView) return;
    api<TimelineEvent[]>(`/stocks/${encodeURIComponent(symbol)}/timeline`).then(setEvents).catch(() => setEvents([]));
  }, [inView, symbol]);

  const visible = useMemo(() => {
    const kinds = FILTERS.find((f) => f.id === filter)?.kinds;
    return (events ?? []).filter((e) => !kinds || kinds.includes(e.kind));
  }, [events, filter]);

  // Staggered reveal: animate events in one after another (also replayable with "Play").
  useEffect(() => {
    setRevealed(0);
    if (!visible.length) return;
    let i = 0;
    const t = setInterval(() => {
      i += 1;
      setRevealed(i);
      if (i >= visible.length) clearInterval(t);
    }, Math.max(40, Math.min(160, 2400 / visible.length)));
    return () => clearInterval(t);
  }, [visible]);

  const replay = () => {
    listRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    setRevealed(0);
    let i = 0;
    const t = setInterval(() => {
      i += 1;
      setRevealed(i);
      if (i >= visible.length) clearInterval(t);
    }, 220);
  };

  const first = events?.[0]?.date.slice(0, 4);
  const progress = visible.length ? (revealed / visible.length) * 100 : 0;

  return (
    <section ref={ref} className="panel p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <History className="h-5 w-5 text-accent" />
          <h2 className="text-lg font-semibold text-white">Company journey{first ? ` since ${first}` : ""}</h2>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="seg">
            {FILTERS.map((f) => (
              <button key={f.id} onClick={() => setFilter(f.id)} className={clsx("seg-btn", filter === f.id && "seg-btn-active")}>{f.label}</button>
            ))}
          </div>
          {visible.length > 1 && (
            <button onClick={replay} className="btn text-xs"><Play className="h-3.5 w-3.5" /> Play</button>
          )}
        </div>
      </div>

      {!events && inView && <Loading />}
      {events && visible.length === 0 && <p className="mt-3 text-sm text-muted">No events to show.</p>}

      {visible.length > 0 && (
        <ol ref={listRef} className="relative mt-5 max-h-[520px] overflow-y-auto pl-8 pr-2">
          <span className="absolute left-[15px] top-0 h-full w-px bg-line" aria-hidden />
          <span className="absolute left-[15px] top-0 w-px bg-gradient-to-b from-accent via-gold to-up transition-all duration-300" style={{ height: `${progress}%` }} aria-hidden />
          {visible.map((e, i) => {
            const st = STYLE[e.kind];
            const Icon = st.icon;
            const year = e.date.slice(0, 4);
            const newYear = i === 0 || visible[i - 1].date.slice(0, 4) !== year;
            return (
              <li
                key={`${e.date}-${e.kind}-${i}`}
                className={clsx("relative pb-5 transition-all duration-500", i < revealed ? "translate-x-0 opacity-100" : "translate-x-3 opacity-0")}
              >
                {newYear && <div className="num -ml-8 mb-2 pl-10 text-xs font-semibold text-muted">{year}</div>}
                <span className={clsx("absolute -left-8 grid h-8 w-8 place-items-center rounded-full border", st.color)}>
                  <Icon className="h-4 w-4" />
                </span>
                <div className="ml-2 rounded-xl border border-white/[0.06] bg-black/25 px-4 py-3">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="font-medium text-white">{e.title}</span>
                    <span className="num text-[11px] text-muted">{new Date(e.date).toLocaleDateString("en-IN", { dateStyle: "medium" })}</span>
                  </div>
                  <p className="mt-0.5 text-sm text-slate-300">{e.text}</p>
                  <p className="mt-1 text-[10px] text-muted">Source: {e.source}</p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
      <div className="mt-2">
        <SectionNote>Events from NSE listing data, corporate-action records (from 2005) and daily prices. Incorporation dates are not yet included.</SectionNote>
      </div>
    </section>
  );
}
