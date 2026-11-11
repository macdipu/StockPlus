# ADR 0004 — numpy/pandas are allowed in the analysis and scanner domains
Status: Accepted
**Context.** "Domain must not depend on infrastructure." Indicators are vectorised time-series maths.
**Decision.** numpy/pandas count as computational libraries, not infrastructure, for `analysis.domain` and
`scanner.domain` only. FastAPI, SQLAlchemy, httpx and redis stay forbidden in every domain (import-linter).
**Consequences.** The existing pure, well-tested analytics move over unchanged; other domains stay stdlib-only.
