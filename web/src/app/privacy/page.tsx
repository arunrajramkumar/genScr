import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";
import { CONTACT_EMAIL, SITE_NAME } from "@/lib/site";

export const metadata: Metadata = { title: `Privacy Policy | ${SITE_NAME}` };

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy" updated="23 October 2026">
      <p>
        This policy explains how {SITE_NAME} handles personal data, in line with the Digital Personal Data Protection Act, 2023
        (DPDP Act) and the Information Technology Act, 2000.
      </p>

      <h2>What we collect</h2>
      <ul>
        <li>No accounts, sign-ups or forms: we do not ask for your name, email, phone or financial details.</li>
        <li>
          Technical data such as IP address, browser type and requested pages may be processed briefly by our hosting provider
          for security, rate limiting and to keep the service running.
        </li>
        <li>
          Your browser stores one preference locally (that you have seen the disclaimer notice). It never leaves your device.
        </li>
        <li>We do not use advertising or tracking cookies.</li>
      </ul>

      <h2>How we use it</h2>
      <p>Only to operate, secure and improve the service. We do not sell or share personal data for marketing.</p>

      <h2>Retention</h2>
      <p>Server logs are kept only as long as needed for security and operations, then deleted by the hosting provider.</p>

      <h2>Your rights</h2>
      <p>
        Under the DPDP Act you may request access to, correction or erasure of personal data we hold about you, and raise a
        grievance. We will respond within a reasonable time.
      </p>

      <h2>Grievance officer / contact</h2>
      <p>
        {CONTACT_EMAIL ? <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> : "Contact details will be published here before launch."}
      </p>

      <h2>Changes</h2>
      <p>If we start collecting more data (for example, accounts or analytics), this policy will be updated first.</p>
    </LegalPage>
  );
}
