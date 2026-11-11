# DSE Live Analyzer — Architecture Assessment & Target Design

Status: **accepted plan, migration in progress** · Baseline commit `7508812` (legacy app, 49 tests green)

| Phase | State |
|---|---|
| 0 Foundation | ✅ done (`bc56726`) |
| 1 market_data | ✅ done (`05749b1`) — see below |
| 2 live_feed | ✅ done — see below |
| 3–7 | not started |

**Phase 1 notes.** `market_data` feature: domain (entities, TTM-EPS policy, EOD rule), ports, use cases (Sync, EnsureFresh read-through, Profile, Candles, Announcements, Backfill, AppendEndOfDay), DSE adapter (parser + polite HTTP), Postgres repositories (PAGE-over-SNAPSHOT precedence enforced in SQL), migration `0002_market_data` (drift-checked, reversible), `/api/v1/stocks/{symbol}`, `/candles`, `/announcements`, CLI `python -m dse.cli {sync,backfill,eod}`. Contract test reproduces the legacy output for recorded DSE bytes.
Known gaps carried forward: candles carry no moving averages yet (Phase 3 analysis).

**Phase 2 notes.** `live_feed` feature: domain (`LiveQuote`, `SessionState.is_after_close`, `LiveSnapshot.changes_since`, `PollPolicy`), use cases (`PollSnapshot` with ETag + at-least-once delivery, `RunFeed` loop with backoff, `EndOfDayTrigger`, `GetQuotes`/`GetMarket`/`GetFeedStatus`), per-replica `FeedHub` fan-out (bounded drop-oldest queues), Redis adapters (`live:quotes` hash of deltas, `live:market`, `live:counters`, global `live:seq` event ids, `live:events` channel), `SqlTickRepository` + migration `0003_live_feed`, `/api/v1/quotes`, `/market`, `/feed/status`, `/stream` (SSE). `dse.worker` is the second composition root (`--check` = healthcheck); after the close it runs market_data's `AppendEndOfDay` once per session (Redis `SET NX` guard), which now also fills `instruments.asset_type` (Phase 1 gap closed). Compose: one-shot `migrate`, `api` ×2 (host 8001–8002), one `worker`.
Exit criterion verified two ways: integration test boots two uvicorn servers and asserts the same quote event (same id, same payload) on both SSE streams; and live against DSE, both compose replicas streamed the identical 170 events (ids 1–170) over one upstream tick, ~4 ms worker→bus.
Decisions: payload fields are snake_case like Phase 1 (legacy camelCase `assetType`/`tradeTime` change with the Phase 6 frontend); no `analysis`/`universe` stream events yet (Phases 3/4 add them as worker hooks); SSE does not replay on `Last-Event-ID` (ADR 0006 amendment). Ticks have no retention policy yet (~100k rows/trading day).

Migration strategy: **strangler fig**. The new modular monolith (`backend/`, `frontend/`) is built next to
the legacy app (repo root). Features move one at a time behind the same `/api/v1` contract. The legacy app
keeps serving until the new one reaches parity, then it is deleted. No big-bang rewrite.

---

## 1. Inspection — what exists (legacy, repo root)

| Module | Role | Depends on |
|---|---|---|
| `config.py` | Constants + a few env overrides | — |
| `scraper.py` | HTTP to DSE, flight/snapshot parsing, per-day SQLite cache, normalisation, screenshot | httpx, pandas, sqlite3, playwright (opt) |
| `store.py` | SQLite market store: bars, fundamentals, ticks, backfill, EOD append | scraper, pandas |
| `indicators.py` `patterns.py` `vpa.py` `valuation.py` `setup_score.py` `signals.py` | Analytics | pandas/numpy only (**already pure**) |
| `scanner.py` | Universe frame builder + rule engine + presets + sector/PE analytics | analytics, scraper |
| `service.py` | Single-stock analysis assembly | everything above + `report` |
| `report.py` | HTML/MD/JSON rendering **and** the plain-language summary | plotly, jinja2 |
| `live.py` | Snapshot poller, diff, in-process pub/sub | httpx, scraper |
| `api.py` / `market_api.py` | FastAPI app: models, process state, workers, routes, SSE, static files | all |
| `web/` | Vanilla JS dashboard (`index.html` + `app.js`) sharing globals | — |

## 2. Architectural problems found

| # | Problem | Consequence |
|---|---|---|
| P1 | **Process-local state** (`api.State`, in-memory caches, pub/sub in one event loop) | Cannot run >1 API replica; a restart loses the feed state; worker load competes with request latency (GIL) |
| P2 | **Workers inside the API process** (poller, universe build ≈ 20 s CPU per tick) | API latency spikes during builds; no independent scaling or restart |
| P3 | `scraper.py` mixes transport, parsing, caching, normalisation, presentation helper (screenshot) | Hard to test/replace the DSE adapter; violates SRP |
| P4 | Two ad-hoc SQLite DBs, schema created at import time, **no migrations** | Schema drift, no upgrade path, no concurrency for multiple writers |
| P5 | Domain logic in presentation: `report.summarize()` (business wording/rules) is called by the service layer | Rules duplicated when the Next.js UI needs the same summary |
| P6 | `api.py` holds DTOs, state, workers, error handling and routes (≈500 lines) | Fat controllers; changes ripple |
| P7 | Analytics domain has **no typed entities**: dicts and DataFrames cross every boundary | No compile-time contract; mistakes surface at runtime (e.g. the `==` text-rule bug found by tests) |
| P8 | No auth; no user-owned data (watchlists live in browser `localStorage`) | Not multi-user; nothing to authorise |
| P9 | Frontend: two scripts coupled through globals, no types, no component reuse | Fragile (`window.App` bug), untestable |
| P10 | No lint/format/type-check gates; Python 3.9 | Style and type errors only caught by review/tests |

Kept as-is because they are sound: the pure analytics modules, the scanner rule semantics, the SSE contract,
the RFC 7807 error envelope, `X-Request-ID`, conditional GET with ETag, politeness limits.

## 3. Target structure

```
backend/                              Python 3.11, FastAPI, SQLAlchemy 2 (async), Alembic, Redis
  pyproject.toml                      ruff (lint+format), mypy --strict, pytest, import-linter contracts
  alembic/                            migrations (one head, reviewed)
  src/dse/
    main.py                           composition root: builds the app, wires containers, mounts routers
    worker.py                         composition root for background processes (feed poller, universe builder)
    core/                             cross-cutting, no business rules
      config.py                       pydantic-settings Settings (env, .env, secrets files)
      logging.py                      structured JSON logs + request/trace ids
      errors.py                       DomainError hierarchy → RFC 7807 mapping (single place)
      db.py                           async engine, session factory, SqlAlchemyUnitOfWork base
      cache.py                        Redis client factory
      security.py                     password hashing (argon2), JWT encode/decode
      events.py                       in-process domain event bus (Observer)
      http.py                         versioned router factory, envelope helpers, health endpoints
    shared_kernel/                    value objects used by >1 feature: Symbol, TradingDay, Money-free Price
    features/
      market_data/                    instruments, daily bars, fundamentals, sync
        domain/       entities (Instrument, DailyBar, Fundamentals), value objects, ports (BarRepository,
                      FundamentalsRepository, MarketDataSource), domain services (TTM EPS policy)
        application/  use cases (SyncInstrument, BackfillUniverse, AppendEndOfDay, GetCandles), DTOs, mappers
        infrastructure/ DseHttpSource (Adapter: flight + snapshot parsing), SqlAlchemy repositories + ORM models
        presentation/ router (thin), request/response schemas
        tests/
      live_feed/                      quotes & ticks
        domain/       Quote, Tick, QuoteChanged (domain event), SessionState
        application/  PollSnapshot (diff → events), GetQuotes, RecordTicks
        infrastructure/ RedisQuoteStore, RedisEventBroadcaster (pub/sub), SqlTickRepository
        presentation/ quotes router, SSE stream
      analysis/                       single-instrument analysis
        domain/       indicators, patterns (Strategy per pattern family), vpa, valuation methods (Strategy),
                      setup score, signal policy, summary composer (moved out of report.py — P5)
        application/  AnalyzeInstrument (query), dto + mappers
        presentation/ analysis/brief/vpa routers
      scanner/                        market-wide scans
        domain/       Rule = Specification (and/or composition), Preset catalogue, UniverseRow
        application/  RunScan, RunPreset (queries over the materialised universe), MaterialiseUniverse (command)
        infrastructure/ RedisUniverseStore (versioned snapshot)
        presentation/ scanner + market-analytics routers
      identity/                       users & auth
        domain/       User aggregate, Email/PasswordHash VOs, Role
        application/  Register, Login, Refresh, GetCurrentUser
        infrastructure/ SqlUserRepository
        presentation/ auth router, `current_user` / `require_role` dependencies
      watchlists/                     user-owned data (replaces localStorage)
        domain/       Watchlist aggregate (unique symbols, max size), SavedScan
        application/  CRUD use cases (UoW), depends on market_data **public facade** to validate symbols
        infrastructure/ SqlAlchemy repositories
        presentation/ router
  tests/architecture/                 import-linter + pytest-archon style boundary tests

frontend/                             Next.js (App Router) + TypeScript strict
  src/app/                            thin route files only: layout, (market)/, stock/[symbol]/, scanner/, …
  src/features/<feature>/{components,hooks,services,schemas,types,store,utils,constants}
      stock · market · scanner · data · tools · watchlist · auth · live
  src/shared/
      api/        single API client (fetch wrapper, problem+json → ApiError, auth refresh)
      ui/         design-system primitives (Card, DataTable, Pill, Stat, Chart wrapper)
      lib/        formatting, env (Zod-validated)
  e2e/                                Playwright specs

docker-compose.yml                    postgres, redis, api, worker, frontend (dev); healthchecks on all
```

### Runtime topology (fixes P1/P2)
```
           ┌──────────── worker process ────────────┐
DSE ──────►│ PollSnapshot ─► QuoteChanged events     │──► Redis: quotes hash, pub/sub "quotes",
           │ MaterialiseUniverse (per tick)         │          universe:{version} snapshot
           │ AppendEndOfDay (after close)           │──► Postgres: bars, fundamentals, ticks
           └────────────────────────────────────────┘
api replicas (stateless) ── read Redis/Postgres, SSE fan-out from Redis pub/sub ──► Next.js (RSC + TanStack Query)
```

## 4. Dependency rules (enforced by import-linter in CI)

1. **Layers inside a feature:** `presentation → application → domain`; `infrastructure → application/domain`.
   `domain` imports only stdlib, `shared_kernel`, and (analysis/scanner only) `numpy`/`pandas` as computational
   libraries. Never FastAPI, SQLAlchemy, httpx, redis.
2. **Ports & adapters:** repositories/gateways are `Protocol`s in `domain`; implementations live in
   `infrastructure`; wiring happens only in composition roots (`main.py`, `worker.py`) and per-feature
   `presentation/dependencies.py`.
3. **Between features:** only through the other feature's `application/facade.py` (public use cases + DTOs).
   No imports of another feature's `domain` internals, repositories or ORM models.
4. **No cycles** between features (contract: `independence` + `layers`).
5. `core` imports no feature. Features import `core` and `shared_kernel`.
6. Frontend: `app/` imports `features/*` public `index.ts` only; features import `shared/*` but never another
   feature's internals; ESLint `import/no-restricted-paths` + `boundaries` plugin.

## 5. Naming conventions

| Thing | Convention | Example |
|---|---|---|
| Python modules/packages | `snake_case` | `market_data/application/sync_instrument.py` |
| Use cases | verb-noun class with `__call__`/`execute` | `RunScan`, `AnalyzeInstrument` |
| Ports | noun + role, `Protocol` | `BarRepository`, `MarketDataSource` |
| Adapters | technology + port | `SqlAlchemyBarRepository`, `DseHttpSource`, `RedisQuoteStore` |
| DTOs | `…Dto` (application), `…Response`/`…Request` (presentation schemas) | `CandleDto`, `ScanRequest` |
| Domain events | past tense | `QuoteChanged`, `UniverseMaterialised` |
| Tables | plural `snake_case`; audit cols `created_at/updated_at` | `daily_bars`, `watchlist_items` |
| Migrations | `YYYYMMDD_HHMM_<slug>` | `20261111_1200_market_data_baseline` |
| API paths | `/api/v1/<plural-resource>` kebab-case | `/api/v1/stocks/{symbol}/vpa`, `/api/v1/market/52-week` |
| TS files | components `PascalCase.tsx`, hooks `useX.ts`, others `kebab-case.ts` | `ScanResultsTable.tsx`, `useLiveQuotes.ts` |
| Env vars | `DSE_` prefix, `__` for nesting | `DSE_DATABASE__URL`, `DSE_LIVE__POLL_S` |

## 6. Patterns — where and why (and where not)

| Pattern | Where | Why it earns its place |
|---|---|---|
| Adapter | `DseHttpSource` | DSE has changed site formats before (old site retired); isolate parsing |
| Repository + Unit of Work | market_data, live_feed ticks, identity, watchlists | transactional writes (backfill, EOD, watchlist edits) testable with fakes |
| Specification | scanner rules (`and`/`or` composition) | rules are the domain's core concept; presets are named specifications |
| Strategy | valuation methods, candle-pattern detectors | each method independently testable/configurable |
| Observer / domain events | `QuoteChanged` → tick recording, universe rebuild, SSE fan-out | decouples poller from consumers |
| CQRS (light) | scans/quotes read from materialised Redis views; writes via use cases | reads are 99% of traffic and need ms latency |
| Facade | each feature's `application/facade.py` | the only cross-feature entry point |
| DTO + Mapper | application boundary | presentation never sees entities/ORM rows |
| Factory | `create_app()`, settings-driven adapter factories | test vs prod wiring |
| **Not used:** Saga | — | no distributed transactions: one database, one deployable (modular monolith) |
| **Not used:** generic base repository / service locator | — | no real use case; explicit constructors instead |

## 7. Authentication & authorisation (defaults chosen)

* Market data, analysis and scanners are **public read**. Accounts are needed for user-owned data:
  watchlists, saved scans (and alerts later).
* Email + password (argon2id), short-lived JWT access token (15 min) + rotating refresh token in an
  `HttpOnly; Secure; SameSite=Lax` cookie. Roles: `user`, `admin` (admin: trigger sync, see ops endpoints).
* Secrets only from env / Docker secrets (`DSE_SECURITY__JWT_SECRET`), never committed; `.env.example` documents them.

## 8. Implementation plan (each phase ends green: lint, mypy, tests, boundaries, docker)

| Phase | Scope | Exit criteria |
|---|---|---|
| **0 Foundation** | `backend/` skeleton: pyproject (ruff, mypy strict, pytest, import-linter), `core/` (settings, logging, errors, db, cache, health), Alembic baseline, Dockerfile, docker-compose (postgres, redis, api) | `docker compose up` healthy; `/api/v1/health` + `/ready` (db+redis checks); all gates green |
| 1 market_data | entities, ports, DSE adapter (ported parser + recorded fixtures), SQLAlchemy repos, migrations, sync/backfill/EOD use cases, candles/profile endpoints | contract tests match legacy JSON for the same fixture |
| 2 live_feed | worker poller, Redis quote store + pub/sub, tick repo, quotes + SSE endpoints | 2 API replicas both stream the same tick |
| 3 analysis | move pure analytics into `domain`, summary composer out of report, AnalyzeInstrument | legacy analysis tests pass unchanged against new modules |
| 4 scanner | Specification rules, presets, universe materialisation in worker → Redis, market analytics endpoints | scan p95 < 50 ms; presets identical to legacy results on a fixed universe |
| 5 identity + watchlists | users, JWT, roles, watchlists, saved scans | auth integration tests; 403/401 problem+json |
| 6 frontend | Next.js feature by feature: stock → market → scanner → data → tools → watchlist/auth | Playwright e2e for each tab; no business logic in `app/` |
| 7 cutover | point compose at new stack, delete legacy, ADRs final | legacy removed; README updated |

## 9. Architecture decision records
`docs/architecture/adr/` — 0001 modular monolith + strangler migration · 0002 worker/API split over Redis ·
0003 Postgres + Alembic replaces SQLite · 0004 pandas allowed in analytics domain · 0005 JWT + refresh cookie ·
0006 SSE (not WebSocket) for one-way live data.
