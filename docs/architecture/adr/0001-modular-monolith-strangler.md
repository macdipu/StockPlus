# ADR 0001 — Modular monolith, migrated by strangler fig
Status: Accepted (2026-11-11)
**Context.** One team, one domain (DSE market analytics), one database. Legacy app works and is in use.
**Decision.** A single deployable FastAPI modular monolith with feature modules (`market_data`, `live_feed`,
`analysis`, `scanner`, `identity`, `watchlists`), plus a worker process from the same codebase. Build it beside
the legacy app; move one feature at a time behind the same `/api/v1` contract; delete legacy at parity.
**Consequences.** No network hops or distributed transactions (no Saga needed). Boundaries are enforced by
import-linter instead of by process isolation. Rollback at any phase = keep serving legacy.
