# DSE Live Analyzer — Architecture Assessment & Target Design

Status: **accepted plan, migration in progress** · Baseline commit `7508812` (legacy app, 49 tests green)

| Phase | State |
|---|---|
| 0 Foundation | ✅ done (`bc56726`) |
| 1 market_data | ✅ done (`05749b1`) — see below |
| 2 live_feed | ✅ done — see below |
| 3 analysis | ✅ done — see below |
| 4 scanner | ✅ done — see below |
| 5 identity + watchlists | ✅ done — see below |
| 6 frontend | ✅ done — see below |
| 7 | not started |

**Phase 1 notes.** `market_data` feature: domain (entities, TTM-EPS policy, EOD rule), ports, use cases (Sync, EnsureFresh read-through, Profile, Candles, Announcements, Backfill, AppendEndOfDay), DSE adapter (parser + polite HTTP), Postgres repositories (PAGE-over-SNAPSHOT precedence enforced in SQL), migration `0002_market_data` (drift-checked, reversible), `/api/v1/stocks/{symbol}`, `/candles`, `/announcements`, CLI `python -m dse.cli {sync,backfill,eod}`. Contract test reproduces the legacy output for recorded DSE bytes.
Known gaps carried forward: none from Phase 1 (moving averages are served by `analysis`, see Phase 3).

**Phase 2 notes.** `live_feed` feature: domain (`LiveQuote`, `SessionState.is_after_close`, `LiveSnapshot.changes_since`, `PollPolicy`), use cases (`PollSnapshot` with ETag + at-least-once delivery, `RunFeed` loop with backoff, `EndOfDayTrigger`, `GetQuotes`/`GetMarket`/`GetFeedStatus`), per-replica `FeedHub` fan-out (bounded drop-oldest queues), Redis adapters (`live:quotes` hash of deltas, `live:market`, `live:counters`, global `live:seq` event ids, `live:events` channel), `SqlTickRepository` + migration `0003_live_feed`, `/api/v1/quotes`, `/market`, `/feed/status`, `/stream` (SSE). `dse.worker` is the second composition root (`--check` = healthcheck); after the close it runs market_data's `AppendEndOfDay` once per session (Redis `SET NX` guard), which now also fills `instruments.asset_type` (Phase 1 gap closed). Compose: one-shot `migrate`, `api` ×2 (host 8001–8002), one `worker`.
Exit criterion verified two ways: integration test boots two uvicorn servers and asserts the same quote event (same id, same payload) on both SSE streams; and live against DSE, both compose replicas streamed the identical 170 events (ids 1–170) over one upstream tick, ~4 ms worker→bus.
Decisions: payload fields are snake_case like Phase 1 (legacy camelCase `assetType`/`tradeTime` change with the Phase 6 frontend); no `analysis`/`universe` stream events yet (Phases 3/4 add them as worker hooks); SSE does not replay on `Last-Event-ID` (ADR 0006 amendment). Ticks have no retention policy yet (~100k rows/trading day).

Migration strategy: **strangler fig**. The new modular monolith (`backend/`, `frontend/`) is built next to
the legacy app (removed at the Phase 7 cutover; see git history). Features move one at a time behind the same `/api/v1` contract. The legacy app
keeps serving until the new one reaches parity, then it is deleted. No big-bang rewrite.

**Phase 3 notes.** `analysis` feature. Domain = the legacy analytics moved over verbatim (`indicators`, `patterns`, `vpa`, `valuation`, `setup_score`, `signals`), with pattern detectors split into a `DETECTORS` strategy list, valuation constants moved out of `config.py`, plus two new modules: `frames` (stored bars + live bar → OHLCV frame) and `summary` (the plain-language composer, moved out of `report.py`, P5). Application: `build()` (pure, = legacy `service.build`), `AnalyzeInstrument`/`GetBrief`/`GetTechnicals`/`GetVpa`/`RankSymbols` (pandas runs in a worker thread), Markdown `render_brief`, `AnalysisFacade`. Infrastructure: `FacadeAnalysisInputs` assembles one instrument from the `market_data` and `live_feed` **facades only** (new import-linter contract allows exactly those two imports). Endpoints: `/stocks/{symbol}/analysis`, `/brief`, `/technicals`, `/vpa`, `/screener`. `market_data` facade gained `announcements`.
Exit criterion verified three ways: the 31 legacy analysis tests run unchanged (only import lines edited, kept verbatim under `tests/legacy/`); a golden file produced by the **legacy pipeline on recorded ORIONINFU data** (260 bars, with and without a live bar) is reproduced by the new code for indicators, patterns, levels, trend, valuation, setup, signal, probability and summary; and an end-to-end test (real Postgres + Redis, recorded DSE page) serves every endpoint. Live against DSE: GP analysis in ~0.6 s cold, ~0.2 s warm, identical on both replicas.
Decisions: moving averages are served at `/stocks/{symbol}/technicals` (`market_data` must not import `analysis`, so `/candles` stays raw OHLCV); `fundamentals` in `/analysis` now uses the Phase 1 `FundamentalsDto` shape (nested `shareholding`, `dividend_per_share`, …) instead of the legacy flat dict, and the Markdown brief's fundamentals list follows it; numpy/pandas float output is rounded to 4 dp by `clean()` exactly as legacy `_clean`. pandas resolved to 3.x (legacy ran 2.3): the legacy tests pass on both.
Not ported (deliberately): the legacy per-tick `analysis` SSE event and the intraday (1-minute) VPA — both need tick data and per-subscriber recompute, so they belong with the Phase 4 worker hooks; HTML/plotly report rendering (`report.py` charts) — the Phase 6 frontend draws charts from `/technicals`.

**Phase 4 notes.** `scanner` feature. *Domain:* `Rule` is a Specification (`mask(frame)`), composed with `AllOf`/`AnyOf`; rules validate at construction (`ScanError` → 400 problem+json); `Preset` catalogue of all 41 legacy presets (generated from the legacy table, then owned here); `ScanSpec`/`UniverseFilter`/`Sort`; market analytics (sectors, P/E, 52-week range). *Row maths* stays in `analysis` (`domain/universe_row.py`, a one-line summary of the single-instrument analysis) and is exposed to `scanner` through the analysis facade (`build_universe_rows`, `UniverseInput`). *Application:* `MaterialiseUniverse` (history cached by a cheap signature, last-close view rebuilt only when it can differ, CPU in threads), single-flight `UniverseRefresher` (never blocks the poll loop, collapses bursts into one rebuild), read-side `UniverseView` (one cheap version lookup per request; frames rebuilt only when the worker publishes), `RunScan`/`RunPreset`/analytics. *Infrastructure:* `RedisUniverseStore` (payload + version replaced in one MULTI/EXEC), facade-backed source and notifier. *Worker:* rebuilds after real changes and after the end-of-day write, then broadcasts a `universe` SSE event (via `live_feed`'s new `BroadcastEvent`). *API:* `/scanner/presets[/{key}]`, `/scanner/run`, `/scanner/fields`, `/scanner/universe`, `/market/{sectors,pe,52-week,ta-values,data-matrix}`; `/market/movers` lives in `live_feed` (it owns the quotes). `market_data` gained bulk history (`latest_all` = one window-function query) and a history signature.
Exit criteria verified: **parity** — on a fixed 48-instrument universe (trend/cross/squeeze/breakout/gap/candle/fundamental regimes, run through the *legacy* scanner) the new universe frame matches column-by-column for both views, all 41 presets return the same instruments in the same order wherever the sort keys are distinct, two custom scans and the sector/P-E tables match; the 5 legacy scanner tests run with only their import line changed. **Latency** — p95 8.4 ms (p50 5.9, p99 16.9) over 360 mixed scan requests on a 432-instrument universe, in-process incl. JSON; the first request after a publish rebuilds frames in ~6 ms. Live against DSE: both replicas serve the identical published universe and receive the `universe` event; a preset answers in ~5 ms over real HTTP.
Decisions / deliberate differences from legacy (both are legacy bugs, asserted in tests, not hidden): (1) legacy dropped `asset_type` for quote-less rows and for the whole last-close view, so with the default `assetTypes=EQ` **every pre-market preset returned nothing**; the row now falls back to the instrument record. (2) Ties in a sort are ordered by universe order (stable) instead of legacy's unspecified quicksort order. Payload fields are snake_case (`asset_type`, `asset_types`, `value_mn`).
Superseded: intraday, `/tools/correlation`, `/tools/return` and `/data/{symbol}.csv` were ported later. Never ported: `/stocks/{symbol}/depth` (DSE refuses automated access to it) and the per-tick `analysis` SSE event.
**Test isolation.** Integration suites TRUNCATE tables, so they now run against their own `dse_test` database (created and migrated on demand by `backend/conftest.py`) and Redis db 15. The development database is never touched by `pytest` (an earlier version wiped it).

**Phase 5 notes.** `identity` and `watchlists` features, per ADR 0005 (amended below). *identity:* `Email`/password policy/`User`/`RefreshToken` domain; `Register`, `Login`, `Refresh` (rotating, with reuse detection), `Logout`, `GetCurrentUser`, `PromoteUser`; argon2id + HS256 JWT live in `core/security.py`, the FastAPI dependencies (`CurrentPrincipal`, `require_role`, `AdminOnly`) in `core/auth.py`, and `Principal`/`Role` in `shared_kernel` — so no feature ever imports identity (a contract enforces it). Endpoints `/auth/{register,login,refresh,logout,me}`; operator commands `python -m dse.cli create-user|set-role` (password from a prompt/stdin, never argv). *watchlists:* named `Watchlist` aggregate (unique symbols, ≤100, ≤20 lists/user) and `SavedScan` (≤50/user), unique names per user ignoring case; symbols are checked against DSE's live snapshot via the `live_feed` facade, saved-scan definitions against the scanner's own strict parser via a new `ScannerFacade`. Endpoints `/watchlists…`, `/saved-scans…`; an admin-only `POST /admin/stocks/{symbol}/sync` exercises roles. Migration `0004` (users, refresh_tokens, watchlists, saved_scans; FK `owner_id → users.id ON DELETE CASCADE`; reversible incl. the enum; drift-checked). 13 import-linter contracts.
Verified end to end on Postgres + Redis: cookie attributes, rotation, stolen-token replay revokes the family, concurrent registration of one email creates exactly one account, uniform 401s, lockout, forged/tampered/`alg=none`/expired tokens, cross-user isolation (404 on every verb for both resources), FK cascade, roles (401/403/200).
Bugs the tests caught while writing this phase: a rejected refresh did not clear the cookie (headers on an injected `Response` are dropped when a handler raises), and `"universe": []` passed scan-definition validation (`d.get(..) or {}` treats falsy as missing).
Decisions beyond ADR 0005 are recorded in its amendment. Not done (deliberately): email verification, password reset, and 2FA (no mail transport yet); access tokens of a deactivated user stay valid for ≤15 min; the frontend (Phase 6) is the first consumer.

**Phase 6 notes.** `frontend/` (Next.js 16 App Router, TypeScript strict, TanStack Query, Zod, `lightweight-charts`). `app/` is routing and layout only (one-line route files, providers, the shell); behaviour lives in `features/{auth,live,watchlist,stock,market,scanner,data,tools}`, each with a public `index.ts`; `shared/{api,ui,lib}`. **ESLint enforces the boundaries** (app → feature index only; no feature-to-feature internals; shared imports neither). The browser only talks to Next: `/api/*` is proxied to the API replicas, so the app is same-origin (no CORS; the HttpOnly refresh cookie scoped to `/api/v1/auth` just works) and the SSE stream passes through unbuffered (`compress: false`, verified). Every response is Zod-validated: drift is reported ("Unexpected response"), not rendered. The access token lives in memory only; the refresh cookie restores the session; concurrent 401s share one refresh. The live layer is one `EventSource` per tab over the union of registered symbols (current page first, capped at the API's 50) feeding an external store with per-symbol selectors; `universe` events invalidate scanner/market queries. Watchlist works as a guest (localStorage, as legacy) or on the account, importing a customised guest list at first sign-in. Security headers incl. a CSP are set in `next.config.ts`. Compose gains a `frontend` service (the API origin is a *build* arg, because Next bakes rewrites at build time).
Backend additions made for it (6a): 1-minute intraday bars from recorded ticks (`/stocks/{symbol}/intraday`, VPA-labelled), `/tools/return` (round-trip fees, live exit price), `/tools/correlation`, `/data/{symbol}.csv`.
Verified: 90 unit/component/contract tests (the contract tests parse **real captured API responses** with each feature's schema); **35 Playwright tests against the real stack**, one spec per tab plus accounts, watchlists and saved scans. Bugs the e2e suite found: (1) **a page reload during the silent refresh signed the user out**: the browser aborted the response carrying the rotated cookie and then presented the spent token; the server now grants a short leeway (a just-rotated token is exchanged once more by rotating its unused successor; reuse after the window still revokes the family: ADR 0005 amended); (2) `crore(NaN)` rendered "NaN cr"; (3) a conditionally-called hook in the shell. Test-infrastructure fixes: concurrent pytest sessions deadlocked on the shared `dse_test` database (they now queue behind a file lock), and the p95 latency test now budgets **CPU time per request** instead of wall-clock (7 ms p95 even at load average 18 on 10 cores, where wall-clock reads ~70 ms because the scheduler, not the code, is the bottleneck).
Deliberately not ported: **market depth** (`/stocks/{symbol}/depth`) because it proxies a DSE endpoint that answers automated clients with 403, and the legacy per-tick `analysis` SSE event, replaced by a throttled (≤ 1 per 20 s) refetch of `/analysis` when the price moves. The frontend has one default watchlist in the sidebar; the API supports many named lists and the UI for them is future work.

**Upstream identity.** The DSE adapters (snapshot poller, company pages) identify themselves honestly (`dse-analyzer/1.0 (non-commercial research tool; polite polling…)`, configurable via `DSE_UPSTREAM__USER_AGENT`) instead of imitating a browser as the legacy app did, and send no browser-mimicking headers. DSE accepts this (checked: snapshot 630 quotes, company page OK) while it answers generic tool clients such as plain `curl` with 403. A 403 is now its own error (`UpstreamForbiddenError`, clear message) and the poller waits 15 minutes before knocking again rather than retrying every minute or two. Scraping a site's public pages is still a decision for the operator: check DSE's terms of use, or ask the exchange for authorised data access.

---

## 1. Inspection — what exists (legacy; deleted at the Phase 7 cutover, recoverable from git history)

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
| 7 cutover | point compose at new stack, delete legacy, ADRs final | legacy removed; README updated — **done** |

## 9. Architecture decision records
`docs/architecture/adr/` — 0001 modular monolith + strangler migration · 0002 worker/API split over Redis ·
0003 Postgres + Alembic replaces SQLite · 0004 pandas allowed in analytics domain · 0005 JWT + refresh cookie ·
0006 SSE (not WebSocket) for one-way live data.
