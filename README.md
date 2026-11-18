# DSE Live Analyzer

Live quotes, technical and fundamental analysis, market-wide scanners and watchlists for the **Dhaka Stock
Exchange**, built as a modular monolith (FastAPI + Postgres + Redis) with a Next.js frontend.

**For research only, not investment advice.** Prices, candles, indices and company data come from www.dse.com.bd;
financial statements, director trades and the credit rating come from two third-party public pages. This tool
identifies itself honestly (`DSE_UPSTREAM__USER_AGENT`) and polls politely. Check each site's terms of use before
relying on it (see `docs/ROADMAP.md`, item 1).

```
backend/    FastAPI API + background worker (Python 3.11). Features: market_data, live_feed, analysis, scanner,
            company, charts, identity, watchlists, each domain → application → infrastructure → presentation.
            src/dse/indicators/ is a pure library of 88 technical indicators that any feature can use.
frontend/   Next.js (App Router, TypeScript strict). Sections: Market · Find shares · Stock · Tools, plus accounts.
            Features: stock, market, picks, scanner, data, tools, company, chart, indicators, watchlist, live, auth.
docs/       architecture, migration notes, ADRs (docs/architecture/), roadmap (docs/ROADMAP.md)
.claude/    agent skills for development in Claude Code (fastapi, frontend-design, python-performance-optimization)
```

## Run

```bash
docker compose up -d --build        # db, redis, one-shot migrate, api ×2 (8001-8002), worker, frontend (3000)
open http://localhost:3000
```

First run has no history, so only live prices work. Load history for the instruments you care about by opening
their page (it syncs on demand), or for everything (about 400 polite page loads, roughly 20 minutes). Intraday
share charts are built from prices the worker records, so they fill up while the market is open:

```bash
docker compose exec worker python -m dse.cli backfill        # or: sync GP BATBC
docker compose exec worker python -m dse.cli create-user you@example.com --role admin
```

Development without containers: `docker compose up -d db redis`, then `uvicorn dse.main:app --port 8001` and
`python -m dse.worker` from `backend/` (virtualenv with `pip install -e ".[dev]"`), and
`API_ORIGIN=http://localhost:8001 npm run dev` from `frontend/`. Configuration: `backend/.env.example`.

If your Docker runtime rejects the API's host port range (`invalid host port 8001-8002`), run one API replica on
8001 with the local override: `docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build`.

## What it does

- **Company details** on every share page (`/api/v1/stocks/{symbol}/company`): contacts, capital and loans,
  yearly EPS/NAV/profit and dividends, shareholding snapshots, this year's quarterly EPS, announcements,
  credit rating, full statements (P&L, balance sheet, cash flow), director trades, ratios (each with its
  basis) and plain-language health flags. The exchange's own company page is the main source (the app already
  syncs it); AmarStock and TopStockBD pages add statements, director trades and the rating. Third-party pages
  are fetched politely (one request at a time per host, honest User-Agent, 6 h Redis cache). Check their terms
  of use before relying on them.
- **Charts** (`/api/v1/charts/{symbol}?resolution=&indicators=`, catalog at `/api/v1/charts/indicators`):
  timeframes 1min / 5min / 30min / 1h / D, thirteen chart styles, and 88 indicators from a server-side
  catalog (moving averages, bands, trend, momentum, volatility, volume, price) with searchable picker and
  editable settings. Data comes from the exchange: daily candles from the stored company history, indices
  (DSEX, DS30, DSES) from the exchange's index endpoints (closing values only), and intraday candles from
  prices this app records from the live feed (history starts when the app first ran). The stock page adds an
  **Analysis** level: Off, Basic (moving averages, support/resistance, pattern labels) or Full (adds the trade
  plan: shaded buy zone, stop, targets, watch levels, Bollinger bands, RSI and MACD, beside the written plan).
  Choices are remembered per browser. See `docs/architecture/adr/0007-charts-and-indicator-engine.md`.
- **Candle analysis**: `candle_story` in `/analysis` (and the Markdown brief) says what the last five candles
  show and where to enter, exit, take profit and what to watch.
- **Navigation**: four sections, Market · Find shares · Stock · Tools. "Find shares" holds three views:
  Picks (`/find`), Custom rules (`/find/rules`, the scanner) and All shares table (`/find/table`). Old paths
  (`/picks`, `/scanner/…`, `/data`) redirect permanently. Sections, views, labels and descriptions live in one
  catalog (`frontend/src/shared/lib/navigation.ts`); each view carries a `plan` (`free` today) so a future
  paid tier can gate a view without restructuring routes or menus.
- **Picks** (`/find`, `/api/v1/market/picks`): every share scored for value and entry timing, bucketed
  (buy zone / wait for a pullback / watch / avoid), with include/exclude sector filters such as "all except
  banks and insurance". Scanner filters accept `exclude_sectors` too.
- **Watchlist**: sector filter and opt-in browser notifications (`/api/v1/alerts?symbols=`), e.g.
  "PADMAOIL 196.8 in buy zone (194–197) with a hammer forming. … Stop 189, target 205."
- **For AI agents**: `/llms.txt`; each share page server-renders a "Key facts" block
  (`data-agent="stock-facts"`, `data-field="…"`) and schema.org JSON-LD, and links JSON/Markdown alternates.

Open work and future scope: [docs/ROADMAP.md](docs/ROADMAP.md).

## Test

```bash
cd backend  && ruff check . && ruff format --check . && mypy && lint-imports && pytest   # 1,100+ tests
cd frontend && npm run check                                                            # lint, types, 110+ tests
cd frontend && npm run e2e                                                              # 40+ Playwright tests, real stack
```

Backend integration tests use their own `dse_test` database and Redis db 15 (never your development data) and are
serialised across concurrent runs. See `frontend/README.md` for what the e2e suite needs.

## Status

The 8-phase migration from the original single-process app is complete, and the company, charts, indicators and
picks features were added after it (Phase 8 notes in `docs/architecture/ARCHITECTURE.md`, and ADR 0007) (`docs/architecture/ARCHITECTURE.md` has
per-phase notes and decisions). The legacy app was removed in the cutover; it lives in git history before the
"Phase 7" commit. Its recorded outputs remain as golden fixtures (`legacy_golden_*.json`) that the parity tests check.

Not ported, on purpose: the live order-book depth panel (DSE answers that endpoint with 403 to automated clients)
and the per-tick `analysis` SSE event.
