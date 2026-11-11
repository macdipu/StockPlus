"use client";

import { num, pct, tone } from "@/shared/lib/format";
import { useConnection, useFeed, useLatencyMs, useMarket } from "../hooks/use-live";
import { Card } from "@/shared/ui/Card";

/** The header status: connection dot, session, DSEX and market breadth. */
export function FeedIndicator() {
  const connection = useConnection();
  const feed = useFeed();
  const live = connection === "live" && !feed?.last_error;
  const text =
    connection === "connecting"
      ? "connecting…"
      : connection === "reconnecting"
        ? "reconnecting…"
        : connection === "offline"
          ? "offline"
          : feed?.last_error
            ? "upstream error"
            : "LIVE";
  return (
    <span role="status" aria-live="polite" data-testid="feed-status">
      <span className={`dot ${live ? "live" : connection === "live" ? "err" : ""}`} aria-hidden />
      <span className="small">{text}</span>
    </span>
  );
}

export function MarketStrip() {
  const m = useMarket();
  if (!m) return null;
  const dsex = m.indices.find((i) => i.key === "DSEX");
  const b = m.breadth;
  const total = (b.advanced ?? 0) + (b.declined ?? 0) + (b.unchanged ?? 0) || 1;
  return (
    <>
      <span className="small mute" data-testid="session">
        {m.session.is_open ? `Market open · closes ${m.session.closing ?? "–"}` : `Market closed · ${m.session.phase ?? ""}`}
      </span>
      {dsex ? (
        <span className="small num">
          DSEX <b>{num(dsex.value)}</b> <span className={tone(dsex.change)}>{pct(dsex.percent, 2)}</span>
        </span>
      ) : null}
      {b.advanced != null ? (
        <span className="bar" title={`▲${b.advanced} ▼${b.declined ?? 0} ▬${b.unchanged ?? 0}`} aria-label="Market breadth">
          <i style={{ width: `${((b.advanced ?? 0) / total) * 100}%`, background: "var(--up)" }} />
          <i style={{ width: `${((b.unchanged ?? 0) / total) * 100}%`, background: "var(--mute)" }} />
          <i style={{ width: `${((b.declined ?? 0) / total) * 100}%`, background: "var(--dn)" }} />
        </span>
      ) : null}
    </>
  );
}

export function LatencyCard() {
  const m = useMarket();
  const feed = useFeed();
  const latency = useLatencyMs();
  return (
    <Card title="Latency">
      <div className="small">
        Upstream trade time <b>{m?.trade_time ?? "–"}</b>
      </div>
      <div className="small">
        Last tick → screen <b>{latency == null ? "–" : `${num(latency, 0)} ms`}</b>
      </div>
      <div className="small">
        Feed poll every <b>{feed?.poll_interval_s == null ? "–" : `${feed.poll_interval_s}s`}</b>
      </div>
      <p className="small mute">
        DSE publishes about once a minute behind a 10–15 s CDN cache. New ticks are pushed here the moment they land.
      </p>
    </Card>
  );
}
