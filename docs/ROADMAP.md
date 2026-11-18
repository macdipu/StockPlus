# Future scope

Open work after the company-details, picks and redesign release. Ordered by priority inside each group.
Size is a rough guide: S is under a day, M a few days, L a week or more.

## Before charging for it

| # | Item | Why | What to do | Size |
|---|---|---|---|---|
| 1 | **Data rights** | Company details come from StockNow, AmarStock and TopStockBD public pages. StockNow locks its EPS/NAV/dividend history behind VIP in its own UI, yet its API returns it without a login. Fine for personal research; risky for a paid product. DSE's own terms also apply. | Read each site's terms. Replace with a licensed source, or get written permission. Keep the source list shown on each page. Gate the company feature behind a config switch until cleared. | M |
| 2 | **Paywall and plans** | `plan` exists on every view in `frontend/src/shared/lib/navigation.ts` and is `free` everywhere. Nothing is enforced. | Add a plan to the user account, enforce it in the API (not only the UI), add a paywall component and billing. Candidates for Pro: custom rules with saved scans, the chart's Full analysis level, notifications, full financial statements. | L |

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
| 7 | **Back-test the Picks score** | Weights are rules of thumb, never tested on history. | Replay the score over past sessions, report hit rate and average return per bucket, tune the weights, publish the result in the app. | L |

## Quality and operations

| # | Item | What to do | Size |
|---|---|---|---|
| 8 | Visual check of the redesign | Review light and dark mode and phone width. Move the fixed chart colours in `TradingChart.tsx` and `chart-model.ts` onto the theme tokens. | S |
| 9 | Browser tests for new features | Picks and sector filters, notifications, company details. Add a contract test that runs the three site parsers on a schedule to catch page changes. | M |
| 10 | Push and deploy | Push `main`, open a pull request. Fold `docker-compose.local.yml` into a documented dev profile. Add a production deployment setup (secrets, domain, TLS, backups). | M |

## Notes

- Every Picks, alert and candle reading is research output, not investment advice. Keep that wording through any paid launch.
- The three skills in `.claude/skills/` (fastapi, frontend-design, python-performance-optimization) are for development in Claude Code.
