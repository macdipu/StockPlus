# ADR 0006 — Server-Sent Events, not WebSocket, for live data
Status: Accepted
**Context.** Data flows one way (server → browser). Upstream DSE ticks about once a minute (CDN max-age 10–15 s).
**Decision.** SSE (`/api/v1/stream`) with typed events, `Last-Event-ID`-compatible ids, heartbeats, and bounded
per-client queues that drop the oldest events for slow clients.
**Consequences.** Works through proxies and HTTP/2 with auto-reconnect built into `EventSource`; no socket
protocol to maintain. If two-way messaging is ever needed (alerts acknowledgement), revisit.
