"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { UserMenu } from "@/features/auth";
import { FeedIndicator, LatencyCard, MarketStrip } from "@/features/live";
import { SymbolSearch } from "@/features/stock";
import { WatchlistCard, useWatchlist } from "@/features/watchlist";
import { buildUrl } from "@/shared/api";
import { Card } from "@/shared/ui/Card";

function currentSymbol(pathname: string): string | null {
  const m = /^\/stock\/([^/]+)/.exec(pathname);
  return m?.[1] ? decodeURIComponent(m[1]).toUpperCase() : null;
}

/** Header, tabs, sidebar. Layout only: every piece of behaviour lives in a feature. */
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const symbol = currentSymbol(pathname);
  const watched = useWatchlist().symbols; // hooks are called unconditionally, then used below
  const target = symbol ?? watched[0];
  const stockHref = target ? `/stock/${target}` : "/stock";
  const tabs = [
    { href: "/", label: "Dashboard", on: pathname === "/" },
    { href: stockHref, label: "Stock", on: pathname.startsWith("/stock") },
    { href: "/scanner", label: "Scanner", on: pathname.startsWith("/scanner") },
    { href: "/data", label: "Data", on: pathname.startsWith("/data") },
    { href: "/tools", label: "Tools", on: pathname.startsWith("/tools") },
  ];
  return (
    <>
      <header className="topbar">
        <Link href="/" className="brand">DSE Live Analyzer</Link>
        <nav className="tabs" aria-label="Main">
          {tabs.map((t) => (
            <Link key={t.label} href={t.href} aria-current={t.on ? "page" : undefined}>{t.label}</Link>
          ))}
        </nav>
        <FeedIndicator />
        <MarketStrip />
        <SymbolSearch />
        <UserMenu />
      </header>
      <div className="layout">
        <aside aria-label="Sidebar">
          <WatchlistCard current={symbol} />
          <LatencyCard />
          <Card title="For AI agents">
            <div className="small">
              {symbol ? (
                <>
                  <a href={buildUrl(`/stocks/${symbol}/analysis`)} target="_blank" rel="noreferrer">analysis.json</a>{" · "}
                  <a href={buildUrl(`/stocks/${symbol}/brief`)} target="_blank" rel="noreferrer">brief.md</a>{" · "}
                </>
              ) : null}
              <a href={buildUrl("/openapi.json")} target="_blank" rel="noreferrer">API schema</a>
            </div>
          </Card>
        </aside>
        <main id="main">{children}</main>
      </div>
      <footer className="footer">For research only, not investment advice. Data: www.dse.com.bd.</footer>
    </>
  );
}
