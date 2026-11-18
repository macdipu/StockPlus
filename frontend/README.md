# DSE Live Analyzer — frontend

Next.js (App Router) + TypeScript (strict) + TanStack Query + Zod. Charts: `lightweight-charts`.

```
src/
  app/            routing and layout ONLY (one-line route files, providers, the shell)
  features/<f>/   auth · live · watchlist · stock · market · picks · scanner · data · tools · company
                  · chart · indicators
                  each: components/ hooks/ services/ schemas/ utils/ store/  + a public index.ts
  shared/         api/ (client, errors, token, shared schemas)  ui/  lib/ (format, env, navigation, local-store)
e2e/              Playwright specs, one per section (+ auth, watchlists, saved scans)
```

**Navigation** (sections, views, labels, descriptions and the `plan` each view belongs to) is one catalog,
`src/shared/lib/navigation.ts`. Menus, section headers and in-app links read from it.

**Charts.** `chart` is generic: give it a symbol and it draws candles, the chosen style (13) and indicators.
`indicators` owns the catalog, the searchable picker and parameter editing; `chart` uses it through its public
index. A host feature adds its own lines, markers and bands through `annotations` (the stock page draws its trade
plan this way; the Market page draws none). Indicator values are computed by the API, so a new backend indicator
needs no frontend change. A chart's style and indicators are one serializable `ChartSpec`, remembered per browser.

**Boundaries are enforced by ESLint** (`npm run lint`): `app/` imports a feature only through its `index.ts`; a
feature never imports another feature's internals or `app/`; `shared/` imports neither.

**API.** The browser only talks to this server: `/api/*` is proxied to the FastAPI replicas (`API_ORIGIN`, read at
*build* time by Next), so everything is same-origin: no CORS, and the refresh cookie (HttpOnly, `Path=/api/v1/auth`)
just works. Every response is validated with Zod; a response that does not match is reported, not rendered.
The access token lives in memory only; the refresh cookie restores the session after a reload.

## Run

```bash
docker compose up -d db redis          # from the repo root; add `migrate api worker` (or just `up -d`) for the API
API_ORIGIN=http://localhost:8001 npm run dev
```

## Test

```bash
npm run check        # eslint + tsc + vitest (unit, component and API-contract tests; no backend needed)
npm run e2e          # Playwright against the REAL stack (builds and starts Next on :3100)
```

`e2e` needs the API on `:8001` (override with `E2E_API_ORIGIN`) and a few synced instruments (`GP`, `BATBC`,
`SQURPHARMA`, `ORIONINFU`): read `/api/v1/stocks/<SYMBOL>` once each, or run `python -m dse.cli backfill`. The
suite creates throwaway accounts (`e2e-*@example.test`) and removes them afterwards.

The contract tests parse real API responses stored in `src/shared/api/__fixtures__/` (analysis, company, picks,
chart, indicator catalog, and others). Refresh them when a backend DTO changes: run the stack and save the
response, for example `curl localhost:8001/api/v1/charts/GP?indicators=rsi > src/shared/api/__fixtures__/chart.json`.
