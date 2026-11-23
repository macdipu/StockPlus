"use client";

import { useMarket } from "@/features/live";
import { int, num, pct, tone } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";

const INDEX_KEYS = ["DSEX", "DS30", "DSES"] as const;

const asNumber = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** The first thing the Market page says: where the indices are, how broad the move is, and how much traded. */
export function MarketSummary() {
  const m = useMarket();
  if (!m) return null;
  const b = m.breadth;
  const up = b.advanced ?? 0;
  const down = b.declined ?? 0;
  const flat = b.unchanged ?? 0;
  const total = up + down + flat || 1;
  const turnover = asNumber(m.totals.turnover);
  const volume = asNumber(m.totals.volume);
  const trades = asNumber(m.totals.trades);
  const lead = up === down ? "Evenly split" : up > down ? "More shares rising than falling" : "More shares falling than rising";
  return (
    <Card title={m.session.is_open ? "Market right now" : "Market at the last close"}>
      <div className="kv">
        {INDEX_KEYS.map((k) => {
          const i = m.indices.find((x) => x.key === k);
          return i ? (
            <div key={k}>
              <span>{k}</span>
              <b className="num">{num(i.value)}</b> <span className={`small ${tone(i.percent)}`} style={{ display: "inline" }}>{pct(i.percent, 2)}</span>
            </div>
          ) : null;
        })}
        <div><span>Turnover</span><b className="num">{turnover == null ? "–" : `${int(turnover)} mn Tk`}</b></div>
        <div><span>Volume</span><b className="num">{volume == null ? "–" : int(volume)}</b></div>
        <div><span>Trades</span><b className="num">{trades == null ? "–" : int(trades)}</b></div>
      </div>
      {b.advanced != null ? (
        <div style={{ marginTop: 14 }}>
          <div className="small">
            {lead}: <b className="up">{up} up</b>, <b className="dn">{down} down</b>, <span className="mute">{flat} unchanged</span>
          </div>
          <span className="bar" style={{ width: "100%", marginTop: 6 }} role="img" aria-label={`${up} advancing, ${down} declining, ${flat} unchanged`}>
            <i style={{ width: `${(up / total) * 100}%`, background: "var(--up)" }} />
            <i style={{ width: `${(flat / total) * 100}%`, background: "var(--mute)" }} />
            <i style={{ width: `${(down / total) * 100}%`, background: "var(--dn)" }} />
          </span>
        </div>
      ) : null}
    </Card>
  );
}
