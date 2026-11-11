# DSE Live Analyzer — frontend

Next.js (App Router) + TypeScript (strict) + TanStack Query + Zod. Charts: `lightweight-charts`.

```
src/
  app/            routing and layout ONLY (one-line route files, providers, the shell)
  features/<f>/   auth · live · watchlist · stock · market · scanner · data · tools
                  each: components/ hooks/ services/ schemas/ utils/ store/  + a public index.ts
  shared/         api/ (client, errors, token, shared schemas)  ui/  lib/ (format, env)
e2e/              Playwright specs, one per tab (+ auth/watchlist/saved scans)
```

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

The contract tests parse real API responses stored in `src/shared/api/__fixtures__/`. Refresh them when a backend
DTO changes.
