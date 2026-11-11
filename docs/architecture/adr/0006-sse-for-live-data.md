# ADR 0006 — Server-Sent Events, not WebSocket, for live data
Status: Accepted
**Context.** Data flows one way (server → browser). Upstream DSE ticks about once a minute (CDN max-age 10–15 s).
**Decision.** SSE (`/api/v1/stream`) with typed events, `Last-Event-ID`-compatible ids, heartbeats, and bounded
per-client queues that drop the oldest events for slow clients.
**Consequences.** Works through proxies and HTTP/2 with auto-reconnect built into `EventSource`; no socket
protocol to maintain. If two-way messaging is ever needed (alerts acknowledgement), revisit.
**Amendment (Phase 2).** Ids come from one Redis counter, so they are identical on every replica. Reconnects are
*not* replayed from `Last-Event-ID`: every connect starts with a `snapshot` event holding the full current state,
and quotes are state rather than deltas, so the newest value supersedes anything missed. This keeps the bus as
plain pub/sub (no Redis Stream retention to size). Revisit if an event type ever carries non-idempotent data.
