import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import { DisclaimerNotice } from "@/components/Legal";
import Navbar from "@/components/Navbar";
import { API_URL } from "@/lib/api";
import { DATA_SOURCES, DISCLAIMER, SITE_NAME } from "@/lib/site";
import "./globals.css";

const sans = Inter({ subsets: ["latin"], variable: "--font-sans" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: `${SITE_NAME}: Indian Stock Screener & Analytics`,
  description: "Screen, analyse and compare NSE stocks with fundamentals, quality scores and technicals.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <head>
        {/* Open the API connection (DNS + TLS) while the page is still loading. */}
        <link rel="preconnect" href={API_URL} crossOrigin="anonymous" />
        <link rel="dns-prefetch" href={API_URL} />
      </head>
      <body className="min-h-screen font-sans">
        <Navbar />
        <main className="mx-auto max-w-7xl px-4 py-8">{children}</main>
        <footer className="mx-auto max-w-7xl px-4 pb-24 pt-6 text-xs leading-relaxed text-muted">
          <div className="space-y-3 border-t border-line pt-6">
            <p><strong className="text-slate-400">Disclaimer:</strong> {DISCLAIMER}</p>
            <p><strong className="text-slate-400">Data:</strong> {DATA_SOURCES}</p>
            <p>
              <strong className="text-slate-400">Charts:</strong> TradingView Lightweight Charts™, Copyright (c) 2025 TradingView, Inc.{" "}
              <a href="https://www.tradingview.com/" target="_blank" rel="noopener noreferrer" className="text-slate-400 hover:text-white">tradingview.com</a>
            </p>
            <nav className="flex flex-wrap gap-4 text-slate-400">
              <Link href="/disclaimer" className="hover:text-white">Disclaimer</Link>
              <Link href="/terms" className="hover:text-white">Terms of Use</Link>
              <Link href="/privacy" className="hover:text-white">Privacy Policy</Link>
            </nav>
          </div>
        </footer>
        <DisclaimerNotice />
      </body>
    </html>
  );
}
