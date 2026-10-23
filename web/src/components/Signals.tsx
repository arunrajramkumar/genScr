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
  const pg = n("profit_growth_yoy"), pe = n("pe");

  if (fromHigh !== null && fromHigh > -3) out.push({ text: "Near 52-week high", tone: "up" });
  if (fromHigh !== null && fromHigh < -40) out.push({ text: `${Math.abs(fromHigh).toFixed(0)}% below 52W high`, tone: "down" });
  if (close !== null && sma200 !== null) out.push(close > sma200 ? { text: "Above 200 DMA", tone: "up" } : { text: "Below 200 DMA", tone: "down" });
  if (sma50 !== null && sma200 !== null && close !== null && close > sma50 && sma50 > sma200) out.push({ text: "Strong uptrend", tone: "up" });
  if (rsi !== null && rsi > 70) out.push({ text: "RSI overbought", tone: "down" });
  if (rsi !== null && rsi < 30) out.push({ text: "RSI oversold", tone: "up" });
  if (de !== null && de < 0.05) out.push({ text: "Debt-free", tone: "up" });
  if (de !== null && de > 2) out.push({ text: "High leverage", tone: "down" });
  if (roe !== null && roe > 20) out.push({ text: `High ROE ${roe.toFixed(0)}%`, tone: "up" });
  if (pf !== null && pf >= 7) out.push({ text: "Strong F-score", tone: "up" });
  if (pf !== null && pf <= 3) out.push({ text: "Weak F-score", tone: "down" });
  if (pg !== null && pg > 25) out.push({ text: "Profit growing fast", tone: "up" });
  if (pe === null && toNum(s.market_cap) !== null) out.push({ text: "Loss-making", tone: "down" });
  if (pe !== null && pe > 80) out.push({ text: "Very high P/E", tone: "neutral" });
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
