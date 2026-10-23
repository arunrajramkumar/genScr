/** Single source of truth for branding and legal copy (checked by backend/tests/test_compliance_repo.py). */

export const SITE_NAME = process.env.NEXT_PUBLIC_SITE_NAME ?? "genScr";

/** Grievance / contact address shown on legal pages. Set NEXT_PUBLIC_CONTACT_EMAIL before launch. */
export const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL ?? "";

/**
 * Forward-looking return scenarios (the "5-year outlook") are OFF unless explicitly enabled.
 * Projections of future returns for specific securities can amount to research/advice under
 * SEBI rules; enable only after legal review.
 */
export const ENABLE_PROJECTIONS = process.env.NEXT_PUBLIC_ENABLE_PROJECTIONS === "true";

export const DATA_SOURCES = "End-of-day prices from NSE bhavcopy files; financials from companies' exchange filings (XBRL).";

export const DISCLAIMER_SHORT = "Educational data only. Not investment advice.";

export const DISCLAIMER =
  `${SITE_NAME} provides market data and analytics for educational and informational purposes only. ` +
  "It is not investment advice, research, or a recommendation to buy, sell or hold any security. " +
  `${SITE_NAME} is not registered with SEBI as an investment adviser or research analyst, and is not affiliated with NSE, BSE or SEBI. ` +
  "Prices are end-of-day and may be delayed or contain errors. Past performance does not indicate future results. " +
  "Do your own research and consult a SEBI-registered investment adviser before investing.";

/** Days after which displayed prices are flagged as possibly outdated. */
export const STALE_AFTER_DAYS = 5;
