"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3 } from "lucide-react";
import clsx from "clsx";
import SearchBox from "./SearchBox";
import { SITE_NAME } from "@/lib/site";

const LINKS = [
  { href: "/", label: "Markets" },
  { href: "/indices", label: "Indices" },
  { href: "/screener", label: "Screener" },
  { href: "/compare", label: "Compare" },
  { href: "/calendar", label: "Calendar" },
  { href: "/watchlist", label: "Watchlist" },
];

export default function Navbar() {
  const path = usePathname();
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-bg/80 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
        <Link href="/" className="flex shrink-0 items-center gap-2 font-bold tracking-tight text-white">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-accent to-emerald-400 text-bg">
            <BarChart3 className="h-4 w-4" />
          </span>
          <span className="hidden sm:inline">{SITE_NAME}</span>
        </Link>
        <nav className="order-last -mx-1 flex w-full items-center gap-1 overflow-x-auto md:order-none md:mx-0 md:w-auto">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={clsx(
                "whitespace-nowrap rounded-lg px-3 py-1.5 text-sm transition",
                (l.href === "/" ? path === "/" : path.startsWith(l.href)) ? "bg-white/10 text-white" : "text-muted hover:text-white",
              )}
            >
              {l.label}
            </Link>
          ))}
        </nav>
        {path !== "/" && (
          <div className="ml-auto min-w-0 flex-1 md:max-w-sm">
            <SearchBox />
          </div>
        )}
      </div>
    </header>
  );
}
