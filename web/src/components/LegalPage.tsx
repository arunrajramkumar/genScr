import type { ReactNode } from "react";

export function LegalPage({ title, updated, children }: { title: string; updated: string; children: ReactNode }) {
  return (
    <article className="mx-auto max-w-3xl space-y-6 text-sm leading-relaxed text-slate-300 [&_h2]:mt-8 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-white [&_li]:ml-5 [&_li]:list-disc [&_a]:text-accent">
      <header>
        <h1 className="text-3xl font-bold text-white">{title}</h1>
        <p className="mt-1 text-xs text-muted">Last updated {updated}</p>
      </header>
      {children}
    </article>
  );
}
