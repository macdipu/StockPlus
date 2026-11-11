# DSE Live Analyzer

Live analysis of Dhaka Stock Exchange instruments, sourced from the official site **www.dse.com.bd**:
a web dashboard, a versioned REST API with a live SSE stream, market-wide scanners, and machine-readable
output for AI agents.

**For research only, not investment advice.**

## Quick start
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py sync          # one-time: history + fundamentals for every equity & mutual fund (~20 min, polite)
python main.py serve         # http://127.0.0.1:8000  (API docs at /docs)
pytest -q
```
CLI without the server: `python main.py ORIONINFU` writes `reports/ORIONINFU.{html,json,md}`;
`--json` / `--brief` print to stdout for agents.

## Architecture
```
www.dse.com.bd ──► scraper.py ─────► store.py (SQLite: bars, fundamentals, ticks)
  /company/{SYM}     parse flight         ▲            │
  /api/live/snapshot  payload, quotes     │            ▼
  /api/live/depth                   live.py ──► market_api.Universe (1 analysed row / instrument,
                                    poller,      rebuilt once per tick, single-flight)
                                    ETag, diff,        │
                                    pub/sub            ▼
indicators · patterns · vpa · valuation · setup_score · signals   (pure, unit-tested)
          ▲                                  ▲
       service.py (one stock)            scanner.py (rules engine + presets)
          ▲                                  ▲
       api.py  ── /api/v1 (REST, SSE) ── market_api.py ──► web/ (dashboard)
```
* **Data layer** (`scraper.py`, `store.py`) knows DSE's payloads; nothing above it does. Every URL/key is in `config.py`.
* **Analysis** modules are pure functions over DataFrames — no I/O, all covered by tests.
* **Live feed** (`live.py`): one poller for the whole market, conditional GET (ETag → 304), per-quote diff,
  fan-out to bounded per-client queues (a slow client drops its oldest events; it never stalls the feed).
* **Universe worker**: rebuilt once per upstream tick in a thread, versioned; scans read it in milliseconds.

### How "real time" works (and its limit)
DSE has no public WebSocket. Its own site polls `/api/live/snapshot`, served by CloudFront with
`max-age=10, s-maxage=15`; the trade time inside advances about **once a minute**. We poll every 10 s
(60 s when closed) and push each new tick to browsers over SSE immediately — measured **~10–100 ms from tick
arrival to browser**. Polling faster cannot make DSE publish faster; it only re-reads the CDN cache.

## API (v1)
Success: `{"data": …, "meta": {requestId, tradeTime, …}}` · Errors: RFC 7807 `application/problem+json`
with `requestId` · Every response: `X-Request-ID`, `Server-Timing`. Full schema at `/docs`.

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/health`, `/ready`, `/universe/status` | Liveness; readiness (feed freshness → 503 if stale); store/universe state |
| `GET /api/v1/market` | Session, indices, breadth, totals, movers |
| `GET /api/v1/quotes?symbols=` | Live quotes (all or a list) |
| `GET /api/v1/market/sectors` · `/movers?by=` · `/pe` · `/52-week` | Sector performance; gainers/losers/value/volume/trades; market/sector/category P/E; 52-week positions |
| `GET /api/v1/market/ta-values` · `/data-matrix` | Indicator values / fundamentals for every instrument |
| `GET /api/v1/stocks/{sym}` · `/candles` · `/announcements` | Profile & fundamentals; OHLCV + MAs (live bar); announcements |
| `GET /api/v1/stocks/{sym}/analysis` · `/brief` | **Agent endpoints**: full knowledge JSON / LLM-sized Markdown |
| `GET /api/v1/stocks/{sym}/depth` | Top-10 bid/ask, spread, order imbalance |
| `GET /api/v1/stocks/{sym}/vpa` · `/intraday` | Daily volume-price analysis; 1-minute bars + VPA from recorded ticks |
| `GET /api/v1/scanner/presets` · `/fields` · `/presets/{key}` | 40 preset scanners; scannable fields; run a preset (filters: categories, sectors, min turnover, live / last close) |
| `POST /api/v1/scanner/run` | Custom scan: rules (`< <= > >= == != between in not_in is_true contains crosses_above crosses_below`), match all/any, universe filter, sort |
| `GET /api/v1/screener?symbols=` | Rank a list by setup score and R/R |
| `GET /api/v1/tools/correlation` · `/tools/return` · `/data/{sym}.csv` | Return correlation matrix; return calculator (fees); OHLCV download |
| `GET /api/v1/stream?symbols=` | **SSE**: `snapshot`, `quote`, `analysis`, `market`, `universe`, `heartbeat` |

## Feature coverage vs StockNow / AmarStock
Built from public DSE data with our own analytics. Nothing is copied from those sites and no paid content is accessed.

| Their feature | Here |
|---|---|
| Stock page, chart, favorites | Stock view: live price, candlestick + MAs + S/R + pattern markers, watchlist (live) |
| Top shares, latest/sector share price | Market tab: movers, sector table (breadth, turnover share, median P/E, RSI, 1M) |
| Data matrix | Data tab → Data matrix (EPS, P/E, NAV, P/B, yield, sponsor, float, Graham, returns) + CSV export |
| Stock / pre-market / custom scanner | Scanner tab: 40 presets in 8 groups, pre-market mode (last completed session), rule builder, live refresh per tick |
| VPA, 1-minute VPA, VPA watch list | Daily VPA per stock, `vpa_bullish` / `vpa_bearish` scanners, 1-minute VPA from recorded ticks |
| Market depth | Depth panel: top-10 ladder, spread, imbalance (10 s refresh while open) |
| Market / sector / category P/E | `/market/pe` (median and cap-weighted) |
| TA value, trend analysis | Data tab → TA values; per-stock trend table; MA/trend scanners |
| 52-week range, correlation, return calculator, data download | Market & Tools tabs |
| News | Per-stock DSE announcements |
| Signals | BUY/SELL/HOLD with reasons, 6-point setup, trade plan, historical hit rate vs baseline |

**Not built** (no public DSE source, or out of scope): intraday history before the server started recording
(DSE publishes none), MTF/multi-chart galleries, IPO tracker, portfolio, market-wide news archive, training content,
accounts/payments.

## Politeness & data refresh
* `sync`: one page per instrument, sequential, 2.5 s apart, resumable; fundamentals re-fetched when older than 7 days.
* Daily bars after the first sync come from **one** snapshot after the close (`append_eod`), never overwriting
  official page bars.
* Depth is fetched only while someone views that stock (5 s cache).

## Method notes
Indicators, patterns, valuation, setup score and signal rules are documented in their modules
(`indicators.py`, `patterns.py`, `vpa.py`, `valuation.py`, `setup_score.py`, `signals.py`, `scanner.py`).
The short-term probability is a historical frequency on overlapping samples, shown next to the all-days
baseline. It is not a forecast. During the session today's volume is partial, so volume-based readings firm up
toward the close.
