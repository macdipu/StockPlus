"use client";

import { num, pct, tone } from "@/shared/lib/format";
import { useConnection, useFeed, useLatencyMs, useMarket } from "../hooks/use-live";

/** The header status: connection dot, session, DSEX and market breadth. */
export function FeedIndicator() {
  const connection = useConnection();
  const feed = useFeed();
  const m = useMarket();
  const latency = useLatencyMs();
  const detail = [
    `DSE trade time: ${m?.trade_time ?? "unknown"}`,
    `Last price reached this screen ${latency == null ? "–" : `${num(latency, 0)} ms`} after DSE published it`,
    `Checked every ${feed?.poll_interval_s ?? "–"} s. DSE publishes about once a minute behind a 10–15 s cache.`,
  ].join("\n");
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
            : "Live";
  return (
    <span role="status" aria-live="polite" data-testid="feed-status" title={detail}>
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
