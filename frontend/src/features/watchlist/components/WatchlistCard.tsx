"use client";

import Link from "next/link";
import { useState } from "react";
import { routes } from "@/shared/lib/navigation";
import { useAllQuotes, useLiveSymbols, useQuote } from "@/features/live";
import { num, pct, tone } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { useFlash } from "@/shared/ui/use-flash";
import { useWatchlistAlerts } from "../hooks/use-alerts";
import { useWatchlist } from "../hooks/use-watchlist";

function Row({ symbol, selected, onRemove }: { symbol: string; selected: boolean; onRemove: () => void }) {
  const q = useQuote(symbol);
  const flash = useFlash(q?.ltp);
  return (
    <li className={`${selected ? "sel" : ""} ${flash}`} data-testid={`watch-${symbol}`}>
      <span>
        <Link href={`/stock/${symbol}`}>
          <b>{symbol}</b>
        </Link>
        <br />
        <span className={`small ${tone(q?.percent)}`}>{pct(q?.percent, 2)}</span>
      </span>
      <span style={{ textAlign: "right" }}>
        <b className="num">{num(q?.ltp)}</b>
        <br />
        <button className="x" type="button" aria-label={`Remove ${symbol}`} onClick={onRemove}>
          ×
        </button>
      </span>
    </li>
  );
}

function Notifications({ symbols }: { symbols: readonly string[] }) {
  const n = useWatchlistAlerts(symbols);
  const latest = n.alerts.slice(0, 4);
  return (
    <div style={{ marginTop: 10 }}>
      {n.state === "unsupported" ? (
        <p className="small mute">This browser cannot show notifications.</p>
      ) : n.state === "blocked" ? (
        <p className="small dn">Notifications are blocked for this site. Allow them in the browser settings.</p>
      ) : (
        <label className="toggle">
          <input type="checkbox" checked={n.state === "on"} onChange={(e) => (e.target.checked ? void n.enable() : n.disable())} />
          Notify me about buy zones, stops and targets
        </label>
      )}
      {latest.length ? (
        <ul className="alerts" aria-label="Latest alerts" data-agent="alerts">
          {latest.map((a) => (
            <li key={a.key} className={a.severity}>
              <Link href={`/stock/${a.symbol}`}><b>{a.symbol}</b></Link> {a.message.replace(`${a.symbol} `, "")}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/** The sidebar watchlist. `current` is the symbol on screen, offered as "+ add current". */
export function WatchlistCard({ current }: { current: string | null }) {
  const w = useWatchlist();
  useLiveSymbols(w.symbols); // keep every watched symbol streaming
  const quotes = useAllQuotes();
  const [sector, setSector] = useState("");
  const sectorOf = (s: string) => quotes.data?.find((q) => q.symbol === s)?.sector ?? "Other";
  const sectors = [...new Set(w.symbols.map(sectorOf))].sort();
  const shown = sector ? w.symbols.filter((s) => sectorOf(s) === sector) : w.symbols;
  const canAdd = current != null && !w.has(current);
  return (
    <Card title="Watchlist">
      {w.symbols.length === 0 && !w.loading ? <p className="small mute">Nothing watched yet. Find some on <Link href={routes.find}>Find shares</Link>.</p> : null}
      {sectors.length > 1 ? (
        <select className="sel small" style={{ width: "100%", marginBottom: 6 }} aria-label="Filter watchlist by sector" value={sector} onChange={(e) => setSector(e.target.value)}>
          <option value="">All sectors ({w.symbols.length})</option>
          {sectors.map((s) => (
            <option key={s} value={s}>{s} ({w.symbols.filter((x) => sectorOf(x) === s).length})</option>
          ))}
        </select>
      ) : null}
      <ul className="watch">
        {shown.map((s) => (
          <Row key={s} symbol={s} selected={s === current} onRemove={() => w.remove(s)} />
        ))}
      </ul>
      {w.error ? <p className="small dn" role="alert">{w.error}</p> : null}
      <button
        className="btn ghost small"
        type="button"
        style={{ marginTop: 8, width: "100%" }}
        disabled={!canAdd}
        onClick={() => current && w.add(current)}
      >
        + add {current ?? "current"}
      </button>
      <Notifications symbols={w.symbols} />
      <p className="small mute" style={{ marginBottom: 0 }}>
        {w.mode === "guest" ? "Saved in this browser. Sign in to keep it on your account." : "Saved to your account."}
      </p>
    </Card>
  );
}
