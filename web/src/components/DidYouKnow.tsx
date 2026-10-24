"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import {
  BadgeCheck, CalendarCheck, CalendarDays, ChevronLeft, ChevronRight, Coins, Crown, Flame, Lightbulb, Mountain, Pause, Play,
  Shield, TrendingDown, TrendingUp, Trophy, Wallet, Zap, ZapOff, type LucideIcon,
} from "lucide-react";
import { api } from "@/lib/api";

interface Fact { id: string; icon: string; title: string; text: string; source: string }

const ICONS: Record<string, LucideIcon> = {
  coins: Coins, flame: Flame, shield: Shield, wallet: Wallet, trending: TrendingUp, "trending-down": TrendingDown,
  calendar: CalendarDays, "calendar-check": CalendarCheck, crown: Crown, trophy: Trophy, zap: Zap, "zap-off": ZapOff, mountain: Mountain,
};

const ROTATE_MS = 7000;

export default function DidYouKnow({ symbol }: { symbol: string }) {
  const [facts, setFacts] = useState<Fact[] | null>(null);
  const [i, setI] = useState(0);
  const [hovered, setHovered] = useState(false);
  const [stopped, setStopped] = useState(false); // explicit pause (WCAG 2.2.2)
  const paused = hovered || stopped;

  useEffect(() => {
    setFacts(null);
    setI(0);
    api<Fact[]>(`/stocks/${encodeURIComponent(symbol)}/facts`).then(setFacts).catch(() => setFacts([]));
  }, [symbol]);

  useEffect(() => {
    if (!facts || facts.length < 2 || paused) return;
    const t = setInterval(() => setI((x) => (x + 1) % facts.length), ROTATE_MS);
    return () => clearInterval(t);
  }, [facts, paused]);

  if (!facts || facts.length === 0) return null;
  const f = facts[i];
  const Icon = ICONS[f.icon] ?? Lightbulb;
  const go = (d: number) => setI((x) => (x + d + facts.length) % facts.length);

  return (
    <aside
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setHovered(true)}
      onBlur={() => setHovered(false)}
      className="panel relative flex h-full flex-col overflow-hidden p-5"
    >
      <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-gold/10 blur-3xl" />
      <div className="relative flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-gold/15 text-gold"><Lightbulb className="h-4 w-4" /></span>
          <span className="text-sm font-semibold text-white">Did you know?</span>
        </div>
        <span className="num text-xs text-muted">{i + 1}/{facts.length}</span>
      </div>

      <div key={f.id} className="relative mt-5 flex-1 animate-fade-up">
        <div className="flex items-center gap-2 text-gold">
          <Icon className="h-5 w-5" />
          <span className="text-xs font-semibold uppercase tracking-[0.14em]">{f.title}</span>
        </div>
        <p className="mt-3 text-lg font-medium leading-snug text-white">{f.text}</p>
        <div className="mt-4 inline-flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-[11px] text-muted">
          <BadgeCheck className="h-3.5 w-3.5 text-up" /> Source: {f.source}
        </div>
      </div>

      <div className="relative mt-5 flex items-center justify-between">
        <div className="flex flex-wrap gap-1.5">
          {facts.map((x, k) => (
            <button
              key={x.id}
              onClick={() => setI(k)}
              aria-label={`Fact ${k + 1}`}
              className={clsx("h-1.5 rounded-full transition-all", k === i ? "w-6 bg-gold" : "w-1.5 bg-white/20 hover:bg-white/40")}
            />
          ))}
        </div>
        <div className="flex gap-1">
          <button onClick={() => setStopped((s) => !s)} className="rounded-md border border-line p-1 text-muted hover:text-white" aria-label={stopped ? "Resume rotating facts" : "Pause rotating facts"} aria-pressed={stopped}>
            {stopped ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
          </button>
          <button onClick={() => go(-1)} className="rounded-md border border-line p-1 text-muted hover:text-white" aria-label="Previous fact"><ChevronLeft className="h-4 w-4" /></button>
          <button onClick={() => go(1)} className="rounded-md border border-line p-1 text-muted hover:text-white" aria-label="Next fact"><ChevronRight className="h-4 w-4" /></button>
        </div>
      </div>
      <p className="relative mt-3 text-[10px] text-muted">Facts are computed from public data and are not investment advice.</p>
      {!paused && facts.length > 1 && (
        <div className="absolute bottom-0 left-0 h-0.5 bg-gold/50" style={{ animation: `grow ${ROTATE_MS}ms linear` }} key={`bar-${i}`} />
      )}
    </aside>
  );
}
