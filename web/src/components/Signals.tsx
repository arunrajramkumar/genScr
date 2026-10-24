import clsx from "clsx";
import { toNum } from "@/lib/format";
import type { Stock } from "@/lib/types";

type Tone = "up" | "down" | "neutral";

/** Plain-language, data-derived observations (not recommendations). */
export function signalsFor(s: Stock): { text: string; tone: Tone }[] {
  const n = (k: keyof Stock) => toNum(s[k] as never);
  const out: { text: string; tone: Tone }[] = [];
  const close = n("close"), sma200 = n("sma_200"), sma50 = n("sma_50"), rsi = n("rsi_14");
  const fromHigh = n("pct_from_52w_high"), de = n("debt_to_equity"), roe = n("roe"), pf = n("piotroski_f");
  const pg = n("profit_growth_yoy"), pe = n("pe"), nm = n("net_margin");

  // Each chip states the threshold it describes. No trend calls, grades or "strong/weak" judgements.
  // Price-based (technical) states are neutral in colour so they can't read as buy/sell cues.
  if (fromHigh !== null && fromHigh > -3) out.push({ text: "Within 3% of 52-week high", tone: "neutral" });
  if (fromHigh !== null && fromHigh < -40) out.push({ text: `${Math.abs(fromHigh).toFixed(0)}% below 52-week high`, tone: "neutral" });
  if (close !== null && sma200 !== null) out.push({ text: close > sma200 ? "Price above 200-day average" : "Price below 200-day average", tone: "neutral" });
  if (sma50 !== null && sma200 !== null) out.push({ text: sma50 > sma200 ? "50-day average above 200-day" : "50-day average below 200-day", tone: "neutral" });
  if (rsi !== null && rsi > 70) out.push({ text: "RSI above 70", tone: "neutral" });
  if (rsi !== null && rsi < 30) out.push({ text: "RSI below 30", tone: "neutral" });
  // Reported financials: factual, coloured like the figures elsewhere on the page.
  if (de !== null && de < 0.05) out.push({ text: "Debt/equity below 0.05", tone: "up" });
  if (de !== null && de > 2) out.push({ text: "Debt/equity above 2", tone: "down" });
  if (roe !== null && roe > 20) out.push({ text: `ROE ${roe.toFixed(0)}%`, tone: "up" });
  if (pf !== null) out.push({ text: `Piotroski F-score ${pf}/9`, tone: "neutral" });
  if (pg !== null && pg > 25) out.push({ text: `Net profit up ${pg.toFixed(0)}% YoY`, tone: "up" });
  // Only when the reported net profit is actually negative (a missing P/E alone can also mean missing data).
  if (nm !== null && nm < 0) out.push({ text: "Net loss in latest financial year", tone: "down" });
  if (pe !== null && pe > 80) out.push({ text: "P/E above 80", tone: "neutral" });
  return out;
}

export default function Signals({ stock }: { stock: Stock }) {
  const list = signalsFor(stock);
  if (!list.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {list.map((s) => (
        <span
          key={s.text}
          className={clsx(
            "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
            s.tone === "up" && "border-up/25 bg-up/[0.08] text-up",
            s.tone === "down" && "border-down/25 bg-down/[0.08] text-down",
            s.tone === "neutral" && "border-gold/25 bg-gold/[0.08] text-gold",
          )}
        >
          <span className={clsx("h-1.5 w-1.5 rounded-full", s.tone === "up" ? "bg-up" : s.tone === "down" ? "bg-down" : "bg-gold")} />
          {s.text}
        </span>
      ))}
    </div>
  );
}
