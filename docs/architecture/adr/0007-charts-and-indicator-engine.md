# 0007. Charts: a standalone indicator engine, a thin charts feature, a generic chart component

Status: accepted

## Context

Share pages and the market page both need charts with many chart styles and a large, growing set of technical
indicators. Indicators are also useful outside charts (scanner rules, alerts, AI agents). The data behind candles
comes from sources whose terms are not settled (ROADMAP item 1), so the source must be replaceable. Expected load
is many concurrent viewers asking for the same popular shares and indicator sets.

## Decision

**1. `dse.indicators`: a pure library, not a feature.** A registry of indicator definitions
(`id, name, group, placement, params, outputs, scale, levels, compute`). `compute(bars, params) -> DataFrame` is
vectorised, causal (row t uses rows 0..t; `repaints=True` marks the exceptions) and stateless. It imports no
feature, framework or I/O (import-linter enforces it). Any feature may use it. Adding an indicator is one
decorated function and its tests.

**2. `features/charts`: delivery only.**
- Port `CandleSource` with three adapters, all on the exchange's own data: daily bars of a company (Postgres,
  through the market_data facade), indices (the exchange's `index-history` and `index-intraday` endpoints,
  closing values only so `ohlc=false`), and intraday bars of a company (ticks recorded from the live feed, through
  the live_feed facade). A small policy picks the source from (symbol kind, resolution); replacing a source, for
  example with a licensed feed, touches one adapter.
- Endpoints: `GET /charts/indicators` (catalog, with a content-hash `version`) and
  `GET /charts/{symbol}?resolution=&indicators=rsi(14),macd`. Stocks and indices (DSEX, DS30, DSES) share them.
- The charts feature never depends on `analysis`, `scanner` or `company`; no feature depends on it.

**3. Content-addressed caching.** Indicator output is cached in Redis under
`chart:{symbol}:{resolution}:{candle fingerprint}:{spec hash}`. New candles produce a new key, so nothing is ever
invalidated. Concurrent requests for one key share one computation (single flight). CPU work runs off the event
loop behind a concurrency cap. Because the engine is stateless it can move to a process pool or a worker queue
without an API change; hot daily charts can be precomputed after the end-of-day write.

**4. A cache-friendly API.** Columnar arrays (one array per series, aligned with the candles, `null` while
warming up), `ETag` derived from the cache key with `304` replies, at most 8 indicators and a cap on candles per
request, parameters validated and clamped by the catalog. Live prices stay out of this API: the page merges the
live candle from the existing SSE stream, so ticks never trigger recomputation.

**5. `frontend/features/chart`: generic and metadata-driven.** It takes a source (symbol, resolution), a
serializable `ChartSpec` (`{style, analysis, indicators[]}`) and optional host-provided annotations (price
lines, markers, shaded bands). It draws indicators from catalog metadata (placement, output kind, scale,
levels), so a new backend indicator needs no frontend change. The stock page supplies its trade plan as
annotations; the market page supplies none. The `ChartSpec` is stored in the browser today and can be stored per
account later (saved layouts and templates, a natural paid feature) without changing its shape.

## Consequences

- One source of truth for indicator numbers across UI, API, agents and (later) scanner and alerts.
- Scaling levers, in order: Redis cache (already content-addressed), single flight, bounded thread pool,
  precomputation in the worker, process pool or queue, CDN for `304`-friendly responses.
- A closes-only series (an index) cannot feed indicators that read open, high, low or volume. The catalog says
  which columns each indicator `requires` (found by perturbing the input, not by a hand-kept list), the chart
  API skips and reports such indicators, and the picker shows why they are unavailable.
- Intraday history of a company exists only from when recording began.
- Not built: indicators that need data beyond one symbol's OHLCV (Advance/Decline, Correlation Coefficient,
  Technical Ratings, Volume Profile). The catalog lists only what can be computed correctly.
- `analysis/domain/indicators.py` keeps its own maths for now (golden parity tests). Moving it onto the engine
  is a later, separate change.
