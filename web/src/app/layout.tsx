import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import Navbar from "@/components/Navbar";
import "./globals.css";

const sans = Inter({ subsets: ["latin"], variable: "--font-sans" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "genScr: Indian Stock Screener & Analytics",
  description: "Screen, analyse and compare NSE stocks with fundamentals, quality scores and technicals.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body className="min-h-screen font-sans">
        <Navbar />
        <main className="mx-auto max-w-7xl px-4 py-8">{children}</main>
        <footer className="mx-auto max-w-7xl px-4 pb-10 pt-6 text-xs leading-relaxed text-muted">
          <div className="border-t border-line pt-6">
            <strong className="text-slate-400">Disclaimer:</strong> genScr provides data and analytics for educational
            and informational purposes only. It is not investment advice or a recommendation to buy or sell any
            security. genScr is not a SEBI-registered investment adviser or research analyst. Prices are end-of-day
            from public NSE files and may be delayed or contain errors. Do your own research or consult a
            SEBI-registered adviser before investing.
          </div>
        </footer>
      </body>
    </html>
  );
}
