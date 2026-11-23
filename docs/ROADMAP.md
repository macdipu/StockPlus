# Future scope

Open work after the company-details, picks, charts-and-indicators and redesign release. Ordered by priority inside each group.
Size is a rough guide: S is under a day, M a few days, L a week or more.

## Before charging for it

| # | Item | Why | What to do | Size |
|---|---|---|---|---|
| 1 | **Data rights** | Prices, candles, indices and the main company data come from the Dhaka Stock Exchange's own site (its terms still apply, and a commercial product likely needs a data licence from the exchange). Statements, director trades and the credit rating come from AmarStock and TopStockBD public pages, which are third-party commercial sites. | Read the DSE's terms and ask about commercial data licensing. Replace the two third-party pages with a licensed source or remove them. Keep the source list shown on each page. | M |
| 2 | **Paywall and plans** | `plan` exists on every view in `frontend/src/shared/lib/navigation.ts` and is `free` everywhere. Nothing is enforced. | Add a plan to the user account, enforce it in the API (not only the UI), add a paywall component and billing. Candidates for Pro: custom rules with saved scans, the chart's Full analysis level and indicator picker, notifications, full financial statements. | L |

## Features that fall short today

| # | Item | Why | What to do | Size |
|---|---|---|---|---|
| 3 | **Alerts that work with the app closed** | Notifications are polled from the open page every 2 minutes, so a closed tab gets nothing. | Move alert checks to the worker. Deliver by web push (service worker), Telegram or email. | L |
| 4 | **Alert settings saved to the account** | The on/off switch and the "already notified" memory live in the browser (localStorage). | Store preferences and sent-alert keys per user in Postgres; per-share rules (buy zone, stop, target). | M |
| 5 | **Search by company name** | Only trading codes work ("GP", not "Grameenphone"). | Add `GET /market/directory` (symbol, name, sector from the universe frame) and use it in the Stock-tab search. | S |

## Accuracy

| # | Item | Why | What to do | Size |
|---|---|---|---|---|
| 6 | **Dividend-adjusted candles** | History is not adjusted for cash dividends, so an ex-dividend drop can read as a bearish candle (seen on SQURPHARMA). | Use adjusted history for patterns, or mark ex-dividend dates and suppress candle signals on them. | M |
| 7 | **Back-test the Picks score** | Weights are rules of thumb, never tested on history. | Replay the score over past sessions, report hit rate and average return per bucket, tune the weights, publish the result in the app. | L First run done: see `docs/research/picks-backtest-2026-11.md` (entry score has a modest real edge; value/pick numbers are biased by today's fundamentals). |

## Quality and operations

| # | Item | What to do | Size |
|---|---|---|---|
| 8 | Visual check of the redesign | Review light and dark mode and phone width. Move the fixed colours (the indicator palette in `chart/utils/model.ts`, the buy-zone and watch colours in `stock/components/StockChart.tsx`) onto the theme tokens. | S |
| 9 | More browser tests | Picks and its sector filters, watchlist notifications. Add a scheduled check that the DSE company page and the two third-party pages still parse, so a page change is noticed. | M |
| 10 | Push and deploy | Push `main`, open a pull request. Fold `docker-compose.local.yml` into a documented dev profile. Add a production deployment setup (secrets, domain, TLS, backups). | M |
| 11 | Use the indicator engine beyond charts | Let the scanner's rule builder and alerts use any of the 88 indicators ("Supertrend flips up", "RSI(14) < 30") through the same catalog and picker. Move the analysis feature's own indicator maths onto the engine, keeping its golden parity tests. | M |
| 12 | Index candles and volume | Indices have closing values only, so index charts are line-style and 50 indicators are unavailable for them. Needs a source with open, high, low and volume (or build daily index candles from recorded intraday values). | M |

## Notes

- Every Picks, alert and candle reading is research output, not investment advice. Keep that wording through any paid launch.
- The three skills in `.claude/skills/` (fastapi, frontend-design, python-performance-optimization) are for development in Claude Code.
- Intraday candles for shares come from prices this app records, so a new install has no intraday history. Backfill options: record continuously from install day (already done), or a licensed intraday feed.
- Indices have closing values only. Index candles and volume indicators need a source with open, high, low and volume.
- Company details are thinner than they were with a third-party aggregator, because the exchange publishes less: shareholding as three snapshots (not monthly), quarterly EPS for the current year only, and cash flow per share only through TopStockBD.
