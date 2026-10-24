"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { GitCompare, Share2, Star, X } from "lucide-react";
import { SectionNote, StaleDataBanner } from "@/components/Legal";
import { ErrorNote, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { changeClass, fmtNum, fmtPct, fmtPrice } from "@/lib/format";
import { WATCHLIST_MAX, mergeSymbols, normalizeSymbols, toggleSymbol, useWatchlist } from "@/lib/watchlist";

type WatchRow = {
  symbol: string;
  name: string;
  as_of: string | null;
  close: number | null;
  change_pct: number | null;
  return_1y: number | null;
  pe: number | null;
  dividend_yield: number | null;
  pct_from_52w_high: number | null;
};

type BatchResponse = { stocks: WatchRow[]; missing: string[] };

const COMPARE_MIN = 2;
const COMPARE_MAX = 5;

function Watchlist() {
  const router = useRouter();
  const params = useSearchParams();
  const { symbols, toggle } = useWatchlist();
  const shared = useMemo(() => normalizeSymbols((params.get("s") ?? "").split(",")), [params]);

  const [rows, setRows] = useState<WatchRow[] | null>(null);
  const [missing, setMissing] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // One batch request for the whole list. Keyed on the list so adding or removing refetches.
  const key = symbols.join(",");
  useEffect(() => {
    if (!key) {
      setRows([]);
      setMissing([]);
      return;
    }
    let cancelled = false;
    setError(null);
    api<BatchResponse>(`/stocks/batch?symbols=${encodeURIComponent(key)}`)
      .then((r) => {
        if (!cancelled) {
          setRows(r.stocks);
          setMissing(r.missing);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [key]);

  // Removing a stock hides it at once; the refetch only updates the figures.
  const bySymbol = useMemo(() => new Map((rows ?? []).map((r) => [r.symbol, r])), [rows]);
  const shown = symbols.map((s) => bySymbol.get(s)).filter((r): r is WatchRow => Boolean(r));
  const notFound = missing.filter((s) => symbols.includes(s));
  const latest = shown.reduce<string | null>((max, r) => (r.as_of && (!max || r.as_of > max) ? r.as_of : max), null);

  const newFromShared = shared.filter((s) => !symbols.includes(s));
  const room = WATCHLIST_MAX - symbols.length;

  const importShared = () => {
    const added = mergeSymbols(shared);
    router.replace("/watchlist");
    setNotice(added < newFromShared.length ? `Added ${added} stocks. The watchlist holds up to ${WATCHLIST_MAX}.` : `Added ${added} stocks to your watchlist.`);
  };

  const share = async () => {
    const url = `${window.location.origin}/watchlist?s=${symbols.join(",")}`;
    try {
      await navigator.clipboard.writeText(url);
      setNotice("Link copied. Anyone who opens it can add these stocks to their own watchlist.");
    } catch {
      setNotice(`Copying failed. Share this link instead: ${url}`);
    }
  };

  const compareReady = symbols.length >= COMPARE_MIN && symbols.length <= COMPARE_MAX;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-white"><Star className="h-6 w-6 text-accent" /> Watchlist</h1>
          <p className="mt-1 text-sm text-muted">
            {symbols.length} of {WATCHLIST_MAX} stocks. Latest end-of-day figures for the stocks you have starred.
          </p>
        </div>
        {symbols.length > 0 && (
          <div className="flex flex-wrap gap-2">
            <button onClick={share} className="btn text-xs"><Share2 className="h-3.5 w-3.5" /> Share list</button>
            {compareReady ? (
              <Link href={`/compare?symbols=${symbols.join(",")}`} className="btn-primary text-xs">
                <GitCompare className="h-3.5 w-3.5" /> Compare {symbols.length} stocks
              </Link>
            ) : (
              <span className="self-center text-xs text-muted">
                {symbols.length > COMPARE_MAX ? `Compare takes up to ${COMPARE_MAX} stocks.` : `Add ${COMPARE_MIN - symbols.length} more to compare.`}
              </span>
            )}
          </div>
        )}
      </div>

      {notice && <p role="status" className="panel px-4 py-3 text-sm text-slate-300">{notice}</p>}

      {shared.length > 0 && (
        <section className="panel flex flex-wrap items-center justify-between gap-3 p-4">
          <p className="text-sm text-slate-300">
            A shared list was opened: <span className="num text-white">{shared.join(", ")}</span>.
            {newFromShared.length === 0 ? " All of these are already in your watchlist." : ` ${newFromShared.length} are not in your watchlist yet.`}
          </p>
          <div className="flex gap-2">
            {newFromShared.length > 0 && (
              <button onClick={importShared} disabled={room <= 0} className="btn-primary text-xs">
                Import {Math.min(newFromShared.length, Math.max(room, 0))}
              </button>
            )}
            <button onClick={() => router.replace("/watchlist")} className="btn text-xs">Dismiss</button>
          </div>
        </section>
      )}

      {error && <ErrorNote message={error} />}

      {!error && symbols.length === 0 && (
        <section className="panel flex flex-col items-center gap-3 px-6 py-12 text-center">
          <Star className="h-8 w-8 text-accent" />
          <h2 className="text-base font-semibold text-white">Your watchlist is empty</h2>
          <p className="max-w-md text-sm text-muted">
            Open any stock page and click the star labelled &quot;Add to watchlist&quot;. You can keep up to {WATCHLIST_MAX} stocks here.
          </p>
          <Link href="/screener" className="btn mt-2 text-xs">Browse the screener</Link>
        </section>
      )}

      {!error && symbols.length > 0 && rows === null && <Loading />}

      {!error && symbols.length > 0 && rows !== null && (
        <>
          <StaleDataBanner asOf={latest} />
          <section className="panel overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-muted">
                    <th scope="col" className="px-3 py-2 font-medium">Symbol</th>
                    <th scope="col" className="px-2 py-2 font-medium">Name</th>
                    <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-medium">Price</th>
                    <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-medium">Today</th>
                    <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-medium">1Y</th>
                    <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-medium">P/E</th>
                    <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-medium">Div. yield</th>
                    <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-medium" title="How far today's price is below its 52-week high">From 52W high</th>
                    <th scope="col" className="w-10 px-3 py-2"><span className="sr-only">Remove</span></th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((r) => (
                    <tr key={r.symbol} className="table-row">
                      <td className="px-3 py-2">
                        <Link href={`/stock/${r.symbol}`} className="num font-medium text-white hover:text-accent">{r.symbol}</Link>
                      </td>
                      <td className="max-w-[16rem] truncate px-2 py-2 text-slate-300">{r.name}</td>
                      <td className="num px-3 py-2 text-right">{fmtPrice(r.close)}</td>
                      <td className={clsx("num px-3 py-2 text-right", changeClass(r.change_pct))}>{fmtPct(r.change_pct)}</td>
                      <td className={clsx("num px-3 py-2 text-right", changeClass(r.return_1y))}>{fmtPct(r.return_1y)}</td>
                      <td className="num px-3 py-2 text-right">{r.pe !== null && r.pe > 0 ? fmtNum(r.pe, 1) : "—"}</td>
                      <td className="num px-3 py-2 text-right">{r.dividend_yield === null ? "—" : `${fmtNum(r.dividend_yield)}%`}</td>
                      <td className={clsx("num px-3 py-2 text-right", changeClass(r.pct_from_52w_high))}>{fmtPct(r.pct_from_52w_high)}</td>
                      <td className="px-3 py-2 text-right">
                        <button
                          onClick={() => toggle(r.symbol)}
                          aria-label={`Remove ${r.symbol} from watchlist`}
                          className="rounded-md p-1 text-muted transition hover:bg-white/10 hover:text-white"
                        >
                          <X className="h-4 w-4" aria-hidden="true" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          {notFound.length > 0 && (
            <p className="text-xs text-muted">
              Not found in our data, so not shown: <span className="num">{notFound.join(", ")}</span>. Remove them to clear this note.
            </p>
          )}
        </>
      )}

      <SectionNote>
        Your watchlist is stored only in this browser. It is not saved to an account and does not sync to other devices or browsers.
        Share list creates a link that contains only these symbols.
      </SectionNote>
      <SectionNote>
        Source: genScr end-of-day data (NSE). Figures describe the past and are shown for reference. Nothing on this page is investment advice.
      </SectionNote>
    </div>
  );
}

export default function WatchlistPage() {
  return (
    <Suspense fallback={<Loading />}>
      <Watchlist />
    </Suspense>
  );
}
