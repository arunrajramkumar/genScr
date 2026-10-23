import type { Metadata } from "next";
import Link from "next/link";
import { LegalPage } from "@/components/LegalPage";
import { CONTACT_EMAIL, SITE_NAME } from "@/lib/site";

export const metadata: Metadata = { title: `Terms of Use | ${SITE_NAME}` };

export default function TermsPage() {
  return (
    <LegalPage title="Terms of Use" updated="23 October 2026">
      <p>By using {SITE_NAME} you agree to these terms. If you do not agree, please do not use the site.</p>

      <h2>1. Informational use only</h2>
      <p>
        Content is provided for education and information only and is not investment advice. Read the{" "}
        <Link href="/disclaimer">Disclaimer</Link>, which forms part of these terms.
      </p>

      <h2>2. Acceptable use</h2>
      <ul>
        <li>Personal, non-commercial use of the website.</li>
        <li>No scraping, bulk downloading, automated querying or redistribution of data from the site or its API. Requests are rate-limited.</li>
        <li>No use of the site to publish stock tips, recommendations or promotional claims attributed to {SITE_NAME}.</li>
        <li>No attempts to disrupt, overload or gain unauthorised access to the service (Information Technology Act, 2000).</li>
      </ul>

      <h2>3. Third-party data</h2>
      <p>
        Market data originates from NSE and company filings and remains subject to the rights of its owners. {SITE_NAME} does not
        grant any licence to exchange data.
      </p>

      <h2>4. Availability and changes</h2>
      <p>The service is provided &quot;as is&quot; without warranties and may change or be discontinued at any time.</p>

      <h2>5. Governing law</h2>
      <p>These terms are governed by the laws of India.</p>

      <h2>6. Contact and grievances</h2>
      <p>
        Questions or complaints: {CONTACT_EMAIL ? <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> : "contact details will be published here"}.
        See also the <Link href="/privacy">Privacy Policy</Link>.
      </p>
    </LegalPage>
  );
}
