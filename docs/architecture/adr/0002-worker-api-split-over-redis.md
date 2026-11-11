# ADR 0002 — Separate worker process; API replicas are stateless; Redis is the live bus
Status: Accepted
**Context.** Legacy runs the poller and a ~20 s CPU universe build inside the API process (GIL contention,
single replica, state lost on restart).
**Decision.** `dse.worker` runs PollSnapshot, MaterialiseUniverse and AppendEndOfDay. It writes quotes and the
versioned universe snapshot to Redis and publishes `QuoteChanged` on a Redis channel. API replicas read Redis and
fan SSE out from the channel.
**Consequences.** API latency is independent of builds; API scales horizontally; Redis becomes a hard dependency
(covered by `/ready`).
