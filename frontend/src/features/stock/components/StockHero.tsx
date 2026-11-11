"use client";

import { useQuote } from "@/features/live";
import { int, num, pct, tone } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { Stat } from "@/shared/ui/Stat";
import { useFlash } from "@/shared/ui/use-flash";
import type { Analysis } from "../schemas/analysis";

/** Price header. Shows the live quote when the stream has one, else the analysis' last known price. */
export function StockHero({ analysis }: { analysis: Analysis }) {
  const q = useQuote(analysis.symbol);
  const p = analysis.price;
  const ltp = q?.ltp ?? p.ltp;
  const prev = q?.ycp ?? p.prev_close;
  const change = ltp != null && prev ? ltp - prev : null;
  const changePct = ltp != null && prev ? (ltp / prev - 1) * 100 : null;
  const flash = useFlash(q?.ltp);
  return (
    <Card label="Price">
      <div className="hero">
        <div>
          <div className="mute">
            <b style={{ color: "var(--ink)", fontSize: 18 }} data-testid="stock-symbol">{analysis.symbol}</b>{" "}
            <span>{analysis.name}</span> · <span>Category {analysis.fundamentals.category ?? "?"}</span>
            {analysis.fundamentals.sector ? <span> · {analysis.fundamentals.sector}</span> : null}
          </div>
          <span className={`ltp ${flash}`} data-testid="ltp">{num(ltp)}</span>{" "}
          <span style={{ fontSize: 18, fontWeight: 600 }} className={tone(change)}>
            {change == null ? "" : `${change >= 0 ? "▲ +" : "▼ "}${num(change)}`} ({pct(changePct, 2)})
          </span>
        </div>
        <div className="kv" style={{ flex: 1 }}>
          <Stat label="Open">{num(q?.open ?? p.open)}</Stat>
          <Stat label="High">{num(q?.high ?? p.high)}</Stat>
          <Stat label="Low">{num(q?.low ?? p.low)}</Stat>
          <Stat label="Prev close">{num(prev)}</Stat>
          <Stat label="Volume">{int(q?.volume ?? p.volume)}</Stat>
          <Stat label="Value (mn)">{num(q?.value_mn ?? p.value_mn, 3)}</Stat>
        </div>
      </div>
    </Card>
  );
}
