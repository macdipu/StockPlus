# Future scope

Open work after the Nov 2026 stock-page, chart and rescan releases. Ordered by priority inside each group.
Size is a rough guide: S is under a day, M a few days, L a week or more. Items marked **Done** stay for a release so the
numbering in older notes still means something.

## Before charging for it

| # | Item | Why | What to do | Size |
|---|---|---|---|---|
| 1 | **Data rights** | Prices, candles, indices and the main company data come from the Dhaka Stock Exchange's own site (its terms still apply, and a commercial product likely needs a data licence from the exchange). Statements, director trades and the credit rating come from AmarStock and TopStockBD public pages, which are third-party commercial sites. | Read the DSE's terms and ask about commercial data licensing. Replace the two third-party pages with a licensed source or remove them. Keep the source list shown on each page. | M |
| 2 | **Paywall and plans** | `plan` exists on every view in `frontend/src/shared/lib/navigation.ts` and is `free` everywhere. Nothing is enforced. | Add a plan to the user account, enforce it in the API (not only the UI), add a paywall component and billing. Candidates for Pro: custom rules with saved scans, the chart's Full analysis level and indicator picker, notifications, full financial statements. | L |

## Features that fall short today

| # | Item | Why | What to do | Size |
|---|---|---|---|---|
| 3 | **Alerts that work with the app closed** | Notifications are polled from the open page every 2 minutes, so a closed tab gets nothing. This is the largest feature still missing. | Move alert checks to the worker. Recommended: browser push (no outside account or secret) for signed-in users, with the delivery step swappable so Telegram or email can follow. The worker cannot read a watchlist that lives only in the browser, so alerts need a sign-in. Plan it before building. | L |
| 4 | **Alert settings saved to the account** | The on/off switch and the "already notified" memory live in the browser (localStorage). | Store preferences and sent-alert keys per user in Postgres; per-share rules (buy zone, stop, target). | M |
| 5 | **Search by company name** | **Done.** `GET /market/directory` and a name-aware search on the Stock tab ("grameen" finds GP). | Possible follow-up: fuzzy matching and Bangla names. | S |

## Accuracy

| # | Item | Why | What to do | Size |
|---|---|---|---|---|
| 6 | **Dividend-adjusted candles** | History is not adjusted for cash dividends, so an ex-dividend drop can read as a bearish candle (seen on SQURPHARMA). | Use adjusted history for patterns, or mark ex-dividend dates and suppress candle signals on them. | M |
| 7 | **Back-test the Picks score** | **First run done and published** on the Picks page: `docs/research/picks-backtest-2026-11.md` (`make backtest`). The entry score has a modest real edge; the value and pick numbers are biased by today's fundamentals; one year of history, one market period. | Store fundamentals as of each date so the value score can be tested properly; rerun each quarter as history grows; net of fees; tune the weights only after that. | M |

## Quality and operations

| # | Item | What to do | Size |
|---|---|---|---|
| 8 | Visual check of the redesign | **Mostly done.** Signal, score and zone colours use theme tokens, the new screens were checked in light and dark and at phone width, and several phone overflows were fixed. Still fixed mid-tones: the indicator palette and histogram colours in `chart/utils/model.ts` and the watch colour in `stock/components/StockChart.tsx` (a chart library needs real values, so these need a runtime read of the theme). | S |
| 9 | More browser tests | The Playwright specs were edited for Layers, drawings, the Valuation tab and the tab order, but **not run** in the last sessions: run `npm run e2e` against the real stack first and fix what drifted. Then add specs for Picks and its sector filters, Rescan, the stock Summary, market depth and watchlist notifications. Add a scheduled check that the DSE company page, the depth endpoint and the two third-party pages still parse, so a page change is noticed. | M |
| 10 | Push and deploy | `main` is pushed through the chart work; the stock-page commits after it are local until pushed. Fold `docker-compose.local.yml` into a documented dev profile. Add a production deployment setup (secrets, domain, TLS, backups). | M |
| 11 | Use the indicator engine beyond charts | Let the scanner's rule builder and alerts use any of the 88 indicators ("Supertrend flips up", "RSI(14) < 30") through the same catalog and picker. Move the analysis feature's own indicator maths onto the engine, keeping its golden parity tests. | M |
| 12 | Index candles and volume | Indices have closing values only, so index charts are line-style and 50 indicators are unavailable for them. Needs a source with open, high, low and volume (or build daily index candles from recorded intraday values). | M |

## New items from the Nov 2026 work

| # | Item | Why | What to do | Size |
|---|---|---|---|---|
| 13 | **One buy zone from the backend** | The analysis has two: the trade plan's (from nearby support, drawn on the chart) and the setup plan's tighter range around today's price. The page uses the trade plan's everywhere, pinned by a test, but the API still serves both. | Expose a single buy zone in `/analysis` and keep the other under a clear name. | S |
| 14 | **Test the stock-page ratings** | The four tiles, the Valuation method-fit rules, the technical reading and "what changed" use conventional thresholds that have not been tested on past prices. The page says so. | Extend the back-test machinery: do shares rated Strong/Cheap/Favourable later beat the market? Test the pattern "fit" the same way. Adjust thresholds only on that evidence. | M |
| 15 | **Better peer groups** | Small sectors (Telecom has 3 companies) are too few to call a norm, so the page falls back to the whole market, whose median P/E is distorted by many small weak shares. | Build peers from size and business similarity, or label and show both. | M |
| 16 | **Chart patterns: more kinds, honest odds** | Flags, pennants and cup-and-handle are not detected; measured-move targets are written but not drawn; patterns are daily only; nobody has measured how often they work out. | Add the missing shapes, draw targets, back-test the patterns over history. | M |
| 17 | **Chart drawings saved to the account** | Drawings live in the browser per share and timeframe, so they do not follow the user to another device. | Store them per signed-in user (the saved-scans pattern), keep local storage for guests. | S |
| 18 | **Small chart finishes** | Click a name in "Recent patterns" to jump to that candle; a bottom sheet for Layers on phones; the first intraday time label can still clip. | Do as one pass with a phone check. | S |
| 19 | **DSE time stamps** | The exchange's depth "as of" text matched our server's UTC clock, six hours behind Dhaka time, while other DSE time text looks like Dhaka time. The depth tab therefore shows only our own fetch time. | Work out which zone each DSE time string uses and show them consistently. | S |
| 20 | **Block trades** | Dropped for now: no public source that is also allowed was found (the old exchange pages are gone; the third-party site serves it from a private API). | Revisit with a licensed data source (item 1). | M |

## Notes

- Every Picks, alert and candle reading is research output, not investment advice. Keep that wording through any paid launch.
- The three skills in `.claude/skills/` (fastapi, frontend-design, python-performance-optimization) are for development in Claude Code.
- Intraday candles for shares come from prices this app records, so a new install has no intraday history. Backfill options: record continuously from install day (already done), or a licensed intraday feed.
- Indices have closing values only. Index candles and volume indicators need a source with open, high, low and volume.
- Market depth is served from the exchange's own `/api/live/depth` feed (cached 10 s per share). Only DSE; there is no CSE depth.
- Company details are thinner than they were with a third-party aggregator, because the exchange publishes less: shareholding as three snapshots (not monthly), quarterly EPS for the current year only, and cash flow per share only through TopStockBD.
