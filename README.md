# DSE Live Analyzer

Live quotes, technical and fundamental analysis, market-wide scanners and watchlists for the **Dhaka Stock
Exchange**, built as a modular monolith (FastAPI + Postgres + Redis) with a Next.js frontend.

**For research only, not investment advice.** Data comes from www.dse.com.bd; this tool identifies itself honestly
(`DSE_UPSTREAM__USER_AGENT`) and polls politely. Check the exchange's terms of use before relying on it.

```
backend/    FastAPI API + background worker (Python 3.11): features market_data, live_feed, analysis, scanner,
            identity, watchlists, each domain → application → infrastructure → presentation
frontend/   Next.js (App Router, TypeScript strict): stock · market · scanner · data · tools · accounts
docs/       architecture assessment, 8-phase migration plan, ADRs (docs/architecture/)
```

## Run

```bash
docker compose up -d --build        # db, redis, one-shot migrate, api ×2 (8001-8002), worker, frontend (3000)
open http://localhost:3000
```

First run has no history, so only live prices work. Load history for the instruments you care about by opening
their page (it syncs on demand), or for everything (about 400 polite page loads, roughly 20 minutes):

```bash
docker compose exec worker python -m dse.cli backfill        # or: sync GP BATBC
docker compose exec worker python -m dse.cli create-user you@example.com --role admin
```

Development without containers: `docker compose up -d db redis`, then `uvicorn dse.main:app --port 8001` and
`python -m dse.worker` from `backend/` (virtualenv with `pip install -e ".[dev]"`), and
`API_ORIGIN=http://localhost:8001 npm run dev` from `frontend/`. Configuration: `backend/.env.example`.

## Test

```bash
cd backend  && ruff check . && ruff format --check . && mypy && lint-imports && pytest   # 300+ tests
cd frontend && npm run check                                                            # lint, types, 90 tests
cd frontend && npm run e2e                                                              # 35 Playwright tests, real stack
```

Backend integration tests use their own `dse_test` database and Redis db 15 (never your development data) and are
serialised across concurrent runs. See `frontend/README.md` for what the e2e suite needs.

## Status

The 8-phase migration from the original single-process app is complete (`docs/architecture/ARCHITECTURE.md` has
per-phase notes and decisions). The legacy app was removed in the cutover; it lives in git history before the
"Phase 7" commit. Its recorded outputs remain as golden fixtures (`legacy_golden_*.json`) that the parity tests check.

Not ported, on purpose: the live order-book depth panel (DSE answers that endpoint with 403 to automated clients)
and the per-tick `analysis` SSE event.
