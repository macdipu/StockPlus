"use client";

import Link from "next/link";
import { useLiveSymbols, useQuote } from "@/features/live";
import { num, pct, tone } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { useFlash } from "@/shared/ui/use-flash";
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

/** The sidebar watchlist. `current` is the symbol on screen, offered as "+ add current". */
export function WatchlistCard({ current }: { current: string | null }) {
  const w = useWatchlist();
  useLiveSymbols(w.symbols); // keep every watched symbol streaming
  const canAdd = current != null && !w.has(current);
  return (
    <Card title="Watchlist">
      {w.symbols.length === 0 && !w.loading ? <p className="small mute">Nothing watched yet.</p> : null}
      <ul className="watch">
        {w.symbols.map((s) => (
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
      <p className="small mute" style={{ marginBottom: 0 }}>
        {w.mode === "guest" ? "Saved in this browser. Sign in to keep it on your account." : "Saved to your account."}
      </p>
    </Card>
  );
}
