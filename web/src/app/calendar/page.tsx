"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { CalendarClock, CalendarDays } from "lucide-react";
import { SectionNote, StaleDataBanner } from "@/components/Legal";
import { ErrorNote, Loading, PageLoading } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtPrice, toNum } from "@/lib/format";
import type { EventCategory, EventsResponse } from "@/lib/types";

type Kind = "dividend" | "bonus" | "split" | "rights" | "buyback" | "demerger";

type Action = {
  symbol: string;
  name: string | null;
  sector: string | null;
  kind: Kind;
  ex_date: string;
  record_date: string | null;
  amount: number | null;
  ratio_new: number | null;
  ratio_held: number | null;
  old_fv: number | null;
  new_fv: number | null;
  price: number | null;
  close: number | null;
  dividend_yield: number | null;
  amount_pct: number | null;
};

type Calendar = { as_of: string | null; upcoming: Action[]; recent: Action[] };

// Filter chips map to API kinds. "Other" groups the less common actions.
const FILTERS: { label: string; kinds: Kind[] }[] = [
  { label: "Dividends", kinds: ["dividend"] },
  { label: "Bonus", kinds: ["bonus"] },
  { label: "Split", kinds: ["split"] },
  { label: "Other", kinds: ["rights", "buyback", "demerger"] },
];

/** Date-only ISO string (YYYY-MM-DD) as a local date, so it never shifts a day across time zones. */
const parseDay = (iso: string) => new Date(`${iso}T00:00:00`);
const fmtDay = (iso: string | null) =>
  iso ? parseDay(iso).toLocaleDateString("en-IN", { dateStyle: "medium" }) : "—";

/** Plain, factual description of what happened. No recommendation language. */
function describe(a: Action): string {
  switch (a.kind) {
    case "dividend":
      return `Dividend ${fmtPrice(a.amount)} per share`;
    case "bonus":
      return a.ratio_new && a.ratio_held ? `Bonus ${a.ratio_new}:${a.ratio_held}` : "Bonus issue";
    case "split":
      return toNum(a.old_fv) !== null && toNum(a.new_fv) !== null
        ? `Split ₹${toNum(a.old_fv)} → ₹${toNum(a.new_fv)}`
        : "Split";
    case "rights":
      return [
        a.ratio_new && a.ratio_held ? `Rights ${a.ratio_new}:${a.ratio_held}` : "Rights issue",
        toNum(a.price) !== null ? `at ${fmtPrice(a.price)}` : null,
      ].filter(Boolean).join(" ");
    case "buyback":
      return "Buyback";
    case "demerger":
      return "Demerger";
  }
}

/** Dividend as a percent of the last close, two decimals; null when there is no close. */
const pctOf = (a: Action) => {
  const pct = toNum(a.amount_pct);
  return pct === null ? null : pct.toFixed(2);
};

/** Groups rows under one heading per date, keeping the API's order. */
function byDate<T>(rows: T[], day: (r: T) => string): [string, T[]][] {
  const groups = new Map<string, T[]>();
  rows.forEach((r) => groups.set(day(r), [...(groups.get(day(r)) ?? []), r]));
  return [...groups.entries()];
}

// Filter chips for board meetings. Values are the API's category names.
const EVENT_FILTERS: { label: string; value: EventCategory }[] = [
  { label: "Financial results", value: "results" },
  { label: "Dividend", value: "dividend" },
  { label: "Fund raising", value: "fund_raising" },
  { label: "Other", value: "other" },
];

const EVENT_TEXT: Record<EventCategory, string> = {
  results: "Financial results",
  dividend: "Dividend",
  fund_raising: "Fund raising",
  other: "Other business",
};

/** Board meetings announced to NSE, grouped by date. Own filter and fetch, separate from the actions list. */
function MeetingsSection() {
  const [data, setData] = useState<EventsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<EventCategory[]>([]); // none selected = every purpose

  useEffect(() => {
    let current = true;
    const qs = active.length ? `?category=${active.join(",")}` : "";
    setError(null);
    api<EventsResponse>(`/calendar/events${qs}`)
      .then((d) => current && setData(d))
      .catch((e) => current && setError(e.message));
    return () => {
      current = false;
    };
  }, [active]);

  const toggle = (value: EventCategory) =>
    setActive((s) => (s.includes(value) ? s.filter((x) => x !== value) : [...s, value]));

  const sections: [string, EventsResponse["upcoming"], string][] = data
    ? [
        ["Upcoming", data.upcoming, "Meeting date on or after the latest data date."],
        ["Recent", data.recent, "Meeting date before the latest data date, newest first."],
      ]
    : [];

  return (
    <section className="space-y-4 border-t border-line pt-6">
      <div>
        <h2 className="flex items-center gap-2 text-xl font-bold text-white">
          <CalendarClock className="h-5 w-5 text-accent" /> Board meetings &amp; results
        </h2>
        <p className="mt-1 text-sm text-muted">
          Dates on which companies have announced a board meeting to consider financial results, dividends, fund
          raising or other business.
        </p>
      </div>

      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by meeting purpose">
        {EVENT_FILTERS.map((f) => {
          const on = active.includes(f.value);
          return (
            <button
              key={f.value}
              onClick={() => toggle(f.value)}
              aria-pressed={on}
              className={clsx("chip", on && "border-accent/60 bg-accent/10 text-white")}
            >
              {f.label}
            </button>
          );
        })}
      </div>

      {error ? (
        <ErrorNote message={error} />
      ) : !data ? (
        <Loading label="Loading board meetings…" />
      ) : (
        sections.map(([title, rows, hint]) => (
          <section key={title} className="panel overflow-hidden">
            <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-white">
              {title} <span className="font-normal text-muted">({rows.length})</span>
              <span className="ml-2 text-xs font-normal text-muted">{hint}</span>
            </h3>
            {rows.length === 0 ? (
              <p className="px-4 py-6 text-sm text-muted">No board meetings in this window for the selected purposes.</p>
            ) : (
              byDate(rows, (e) => e.event_date).map(([day, items]) => (
                <div key={day}>
                  <h4 className="bg-white/[0.02] px-4 py-2 text-xs font-medium text-slate-300">{fmtDay(day)}</h4>
                  <ul>
                    {items.map((e, i) => (
                      <li
                        key={`${e.symbol}-${e.category}-${i}`}
                        className="border-b border-line/60 px-4 py-2 text-sm transition hover:bg-white/[0.03]"
                      >
                        <div className="grid grid-cols-[6.5rem_minmax(0,1fr)] items-baseline gap-x-4 md:grid-cols-[8rem_minmax(0,1fr)_12rem]">
                          <Link href={`/stock/${e.symbol}`} className="truncate font-medium text-white hover:text-accent">
                            {e.symbol}
                          </Link>
                          <span className="truncate text-slate-400">{e.name ?? e.symbol}</span>
                          <span className="text-slate-200 md:text-right">{EVENT_TEXT[e.category]}</span>
                        </div>
                        {e.description && <p className="mt-0.5 line-clamp-2 text-xs text-muted">{e.description}</p>}
                      </li>
                    ))}
                  </ul>
                </div>
              ))
            )}
          </section>
        ))
      )}

      <SectionNote>
        Source: NSE event calendar. Board meeting dates and agendas are as announced by the companies and can change
        or be rescheduled; meetings NSE shows as cancelled are left out. Please confirm on nseindia.com before relying
        on a date. This lists announced dates only and is not a forecast of results or payouts.
      </SectionNote>
    </section>
  );
}

export default function CalendarPage() {
  const [data, setData] = useState<Calendar | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<string[]>([]); // chip labels; none selected = all kinds

  const kinds = useMemo(
    () => FILTERS.filter((f) => active.includes(f.label)).flatMap((f) => f.kinds),
    [active],
  );

  useEffect(() => {
    let current = true; // ignore a slower response for a filter that is no longer selected
    const qs = kinds.length ? `?kind=${kinds.join(",")}` : "";
    setError(null);
    api<Calendar>(`/calendar${qs}`)
      .then((d) => current && setData(d))
      .catch((e) => current && setError(e.message));
    return () => {
      current = false;
    };
  }, [kinds]);

  const toggle = (label: string) =>
    setActive((s) => (s.includes(label) ? s.filter((x) => x !== label) : [...s, label]));

  if (error) return <ErrorNote message={error} />;
  if (!data) return <PageLoading />;

  const sections: [string, Action[], string][] = [
    ["Upcoming", data.upcoming, "Ex-date on or after the latest data date."],
    ["Recent", data.recent, "Ex-date before the latest data date, newest first."],
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-white">
          <CalendarDays className="h-6 w-6 text-accent" /> Corporate actions calendar
        </h1>
        <p className="mt-1 text-sm text-muted">
          Dividends, bonus issues, splits and other corporate actions announced for NSE-listed companies, by ex-date.
        </p>
      </div>
      <StaleDataBanner asOf={data.as_of} />

      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by action type">
        {FILTERS.map((f) => {
          const on = active.includes(f.label);
          return (
            <button
              key={f.label}
              onClick={() => toggle(f.label)}
              aria-pressed={on}
              className={clsx("chip", on && "border-accent/60 bg-accent/10 text-white")}
            >
              {f.label}
            </button>
          );
        })}
      </div>

      {sections.map(([title, rows, hint]) => (
        <section key={title} className="panel overflow-hidden">
          <h2 className="border-b border-line px-4 py-3 text-sm font-semibold text-white">
            {title} <span className="font-normal text-muted">({rows.length})</span>
            <span className="ml-2 text-xs font-normal text-muted">{hint}</span>
          </h2>
          {rows.length === 0 ? (
            <p className="px-4 py-6 text-sm text-muted">No actions in this window for the selected types.</p>
          ) : (
            byDate(rows, (a) => a.ex_date).map(([day, items]) => (
              <div key={day}>
                <h3 className="bg-white/[0.02] px-4 py-2 text-xs font-medium text-slate-300">{fmtDay(day)}</h3>
                <ul>
                  {items.map((a, i) => (
                    <li key={`${a.symbol}-${a.kind}-${i}`} className="grid grid-cols-[6.5rem_minmax(0,1fr)] items-baseline gap-x-4 gap-y-0.5 border-b border-line/60 px-4 py-2 text-sm transition hover:bg-white/[0.03] md:grid-cols-[8rem_minmax(0,1fr)_14rem_9rem_10rem]">
                      <Link href={`/stock/${a.symbol}`} className="truncate font-medium text-white hover:text-accent">
                        {a.symbol}
                      </Link>
                      <span className="truncate text-slate-400">{a.name ?? a.symbol}</span>
                      <span className="text-slate-200">{describe(a)}</span>
                      <span className="num text-xs text-muted md:text-right">{a.kind === "dividend" && pctOf(a) !== null ? `${pctOf(a)}% of last price` : ""}</span>
                      <span className="num text-xs text-muted md:text-right">Record date {fmtDay(a.record_date)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))
          )}
        </section>
      ))}

      <MeetingsSection />

      <SectionNote>
        Source: NSE corporate announcements, as published by NSE. This is a factual list of announced actions and is
        not investment advice. Dates and amounts can change after publication, so please verify them on nseindia.com
        before relying on them. &quot;As % of last price&quot; divides the declared dividend per share by the most recent
        closing price in our data; it describes the past and is not a forecast.
      </SectionNote>
    </div>
  );
}
