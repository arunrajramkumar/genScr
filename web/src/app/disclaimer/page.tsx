import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";
import { DATA_SOURCES, DISCLAIMER, SITE_NAME } from "@/lib/site";

export const metadata: Metadata = { title: `Disclaimer | ${SITE_NAME}` };

export default function DisclaimerPage() {
  return (
    <LegalPage title="Disclaimer" updated="23 October 2026">
      <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-amber-100">{DISCLAIMER}</p>

      <h2>Not investment advice</h2>
      <p>
        {SITE_NAME} is an information and analytics tool. Screens, scores, ratios, charts, historical return calculations and
        &quot;Did you know?&quot; facts are mechanical computations on public data. They are not research reports, ratings,
        price targets or recommendations to buy, sell or hold any security, and they do not consider your financial situation,
        objectives or risk tolerance.
      </p>

      <h2>No SEBI registration</h2>
      <p>
        {SITE_NAME} and its operators are not registered with the Securities and Exchange Board of India (SEBI) as an
        Investment Adviser or Research Analyst, and do not provide investment advice or research services as defined under
        SEBI regulations. Consult a SEBI-registered investment adviser before making investment decisions.
      </p>

      <h2>Data sources and accuracy</h2>
      <p>
        {DATA_SOURCES} Data is end-of-day (not real-time), may be delayed, incomplete or contain errors, and derived metrics
        depend on the accuracy of source filings. Always verify information with the exchange or the company&apos;s official
        disclosures before relying on it.
      </p>

      <h2>Historical figures</h2>
      <p>
        Historical returns, CAGR and &quot;what if&quot; calculations use split/bonus-adjusted closing prices and exclude
        dividends, taxes and charges. Past performance does not indicate or guarantee future results.
      </p>

      <h2>No affiliation</h2>
      <p>
        {SITE_NAME} is independent and is not affiliated with, endorsed by or sponsored by the National Stock Exchange of
        India (NSE), BSE Ltd. or SEBI. Exchange and company names are used only to identify the source of data.
      </p>

      <h2>Limitation of liability</h2>
      <p>
        Investing in securities involves risk, including loss of capital. {SITE_NAME} is not liable for any loss or damage
        arising from the use of, or reliance on, information on this site.
      </p>
    </LegalPage>
  );
}
