"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { UserMenu } from "@/features/auth";
import { FeedIndicator, MarketStrip } from "@/features/live";
import { WatchlistCard } from "@/features/watchlist";
import { buildUrl } from "@/shared/api";
import { SECTIONS, sectionFor } from "@/shared/lib/navigation";

function currentSymbol(pathname: string): string | null {
  const m = /^\/stock\/([^/]+)/.exec(pathname);
  return m?.[1] ? decodeURIComponent(m[1]).toUpperCase() : null;
}

/** Header, tabs, sidebar. Layout only: every piece of behaviour lives in a feature. */
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const symbol = currentSymbol(pathname);
  const active = sectionFor(pathname)?.key;
  const tabs = SECTIONS.map((sec) => ({ ...sec, on: sec.key === active }));
  return (
    <>
      <header className="topbar">
        <Link href="/" className="brand">DSE Live Analyzer</Link>
        <nav className="tabs" aria-label="Main">
          {tabs.map((t) => (
            <Link key={t.key} href={t.href} title={t.description} aria-current={t.on ? "page" : undefined}>{t.label}</Link>
          ))}
        </nav>
        <FeedIndicator />
        <MarketStrip />
        <UserMenu />
      </header>
      <div className="layout">
        <aside aria-label="Sidebar">
          <WatchlistCard current={symbol} />
        </aside>
        <main id="main">{children}</main>
      </div>
      <footer className="footer">
        <span>For research only, not investment advice. Prices from the Dhaka Stock Exchange; company data from public sources named on each page.</span>
        <nav aria-label="For developers and AI agents">
          {symbol ? (
            <>
              <a href={buildUrl(`/stocks/${symbol}/analysis`)} target="_blank" rel="noreferrer">{symbol} analysis (JSON)</a>
              <a href={buildUrl(`/stocks/${symbol}/brief`)} target="_blank" rel="noreferrer">{symbol} brief (Markdown)</a>
            </>
          ) : null}
          <a href="/llms.txt" target="_blank" rel="noreferrer">Guide for AI agents</a>
          <a href={buildUrl("/openapi.json")} target="_blank" rel="noreferrer">API reference</a>
        </nav>
      </footer>
    </>
  );
}
