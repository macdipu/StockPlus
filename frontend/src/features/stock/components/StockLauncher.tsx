"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState, useSyncExternalStore, type FormEvent } from "react";
import { useAllQuotes } from "@/features/live";
import { useWatchlist } from "@/features/watchlist";
import { num, pct, tone } from "@/shared/lib/format";
import { routes } from "@/shared/lib/navigation";
import type { Quote } from "@/shared/api";
import { Card } from "@/shared/ui/Card";
import { useNames } from "../hooks/use-stock-queries";
import { matchSymbols } from "../utils/search";
import { clearRecent, getRecent, getServerRecent, subscribeRecent } from "../store/recent-store";

const LIST_SIZE = 6;
const NO_NAMES: ReadonlyMap<string, string> = new Map();

function SymbolRow({ quote, name }: { quote: Quote | undefined; name?: string }) {
  if (!quote) return null;
  return (
    <li>
      <Link href={routes.stock(quote.symbol)}><b>{quote.symbol}</b> <span className="mute small">{name ?? quote.sector ?? ""}</span></Link>
      <span className={tone(quote.percent)}>{num(quote.ltp)} · {pct(quote.percent, 2)}</span>
    </li>
  );
}

function QuoteList({ title, quotes, empty }: { title: string; quotes: readonly Quote[]; empty: string }) {
  return (
    <Card title={title}>
      {quotes.length === 0 ? <p className="mute small" style={{ margin: 0 }}>{empty}</p> : <ul className="watch">{quotes.map((q) => <SymbolRow key={q.symbol} quote={q} />)}</ul>}
    </Card>
  );
}

/** The /stock landing page: search with live suggestions, then shortcuts to where people usually go next. */
export function StockLauncher() {
  const router = useRouter();
  const quotes = useAllQuotes();
  const watchlist = useWatchlist();
  const recent = useSyncExternalStore(subscribeRecent, getRecent, getServerRecent);
  const names = useNames().data ?? NO_NAMES;
  const [value, setValue] = useState("");

  const all = useMemo(() => (quotes.data ?? []).filter((q) => q.ltp != null && q.ltp > 0), [quotes.data]);
  const bySymbol = useMemo(() => new Map(all.map((q) => [q.symbol, q])), [all]);
  const matches = useMemo(() => matchSymbols(all, value, names), [all, value, names]);
  const active = useMemo(() => [...all].sort((a, b) => b.volume - a.volume).slice(0, LIST_SIZE), [all]);
  const gainers = useMemo(() => [...all].filter((q) => q.volume > 0).sort((a, b) => (b.percent ?? 0) - (a.percent ?? 0)).slice(0, LIST_SIZE), [all]);

  function go(symbol: string) {
    router.push(routes.stock(symbol.trim().toUpperCase()));
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    const code = matches[0]?.symbol ?? value.trim();
    if (code) go(code);
  }
  const rows = (symbols: readonly string[]) => symbols.map((s) => bySymbol.get(s)).filter((q): q is Quote => q !== undefined);

  return (
    <>
      <Card title="Look up a stock">
        <form onSubmit={submit} role="search" className="launcher">
          <label className="sr-only" htmlFor="stock-lookup">Trading code, company or sector</label>
          <input
            id="stock-lookup"
            className="inp launcher-input"
            placeholder="Type a trading code, company or sector, e.g. GP, Grameenphone, pharma"
            autoComplete="off"
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
          <button className="btn" type="submit">Open</button>
        </form>
        {value.trim() ? (
          matches.length > 0 ? (
            <ul className="watch" aria-label="Matching symbols">{matches.map((q) => <SymbolRow key={q.symbol} quote={q} name={names.get(q.symbol)} />)}</ul>
          ) : (
            <p className="mute small">{quotes.isPending ? "Loading symbols…" : `No symbol or sector matches “${value.trim()}”. Press Open to try it anyway.`}</p>
          )
        ) : (
          <p className="mute small" style={{ marginBottom: 0 }}>
            Not sure what to look at? Use <Link href={routes.find}>Find shares</Link> to rank every stock by value and entry timing.
          </p>
        )}
      </Card>

      <div className="grid2 launcher-grid">
        <Card title="Recently viewed">
          {recent.length === 0 ? (
            <p className="mute small" style={{ margin: 0 }}>Stocks you open will appear here.</p>
          ) : (
            <>
              <ul className="watch">{rows(recent).map((q) => <SymbolRow key={q.symbol} quote={q} />)}</ul>
              <button type="button" className="btn ghost small" onClick={clearRecent}>Clear</button>
            </>
          )}
        </Card>
        <QuoteList title="Your watchlist" quotes={rows(watchlist.symbols).slice(0, LIST_SIZE)} empty="Add stocks from a stock page to track them here." />
        <QuoteList title="Most active today" quotes={active} empty={quotes.isPending ? "Loading…" : "No trades yet."} />
        <QuoteList title="Top gainers today" quotes={gainers} empty={quotes.isPending ? "Loading…" : "No trades yet."} />
      </div>
    </>
  );
}
