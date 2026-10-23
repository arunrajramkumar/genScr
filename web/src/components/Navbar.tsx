"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3 } from "lucide-react";
import clsx from "clsx";
import SearchBox from "./SearchBox";

const LINKS = [
  { href: "/", label: "Markets" },
  { href: "/screener", label: "Screener" },
  { href: "/compare", label: "Compare" },
];

export default function Navbar() {
  const path = usePathname();
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-bg/80 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
        <Link href="/" className="flex shrink-0 items-center gap-2 font-bold tracking-tight text-white">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-accent to-emerald-400 text-bg">
            <BarChart3 className="h-4 w-4" />
          </span>
          <span className="hidden sm:inline">genScr</span>
        </Link>
        <nav className="flex items-center gap-1">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={clsx(
                "rounded-lg px-3 py-1.5 text-sm transition",
                path === l.href ? "bg-white/10 text-white" : "text-muted hover:text-white",
              )}
            >
              {l.label}
            </Link>
          ))}
        </nav>
        {path !== "/" && (
          <div className="ml-auto w-full max-w-sm">
            <SearchBox />
          </div>
        )}
      </div>
    </header>
  );
}
