# UX refactor plan (Nov 2026)

Source: the full front-end and back-end audit. Items are done in this order; each ends green on
`make test` and a rebuilt stack (`make up`).

| # | Step | Scope | Done when |
|---|------|-------|-----------|
| 0 | Shared freshness + Rescan (`features/universe`) | Label and Rescan on Market, Rules, Table, Picks | Done |
| 1 | Search by company name | `GET /market/directory` (symbol, name, sector, category) from the universe; Stock launcher matches names too | Done: "grameen" finds GP; backend + frontend tests |
| 2 | Merge Price table + Seasonality into one History tab | Stock page has Overview, Technicals, History, Company | Done: Tab in the URL hash; old `#prices` and `#seasonality` links still land on History |
| 3 | Market page opens with a summary | Breadth, turnover and the index move above the five tables | Done: Summary line first, tables below |
| 5 | Theme tokens for signal, buy-zone and score colours | `--sig-*` tokens (own dark shades); Pill, Picks score bar and stock chart zone read tokens | Done |
| 6 | Narrow-screen tables | `hideNarrow` on `DataTable` columns, `.hide-sm` on Picks; secondary columns drop under 700px | Done |
| 4 | Rescan confirmation | "Updated just now" after a successful rescan | Done: Visible for a few seconds, announced to screen readers |

## Backlog (not in this pass)
- Market Depth and Block Trades: waiting on a decision about the data source (DSE refuses automated depth access).
- Alerts from the worker with the app closed, saved per account (roadmap 3, 4).
- Dividend-adjusted candles (roadmap 6), Picks back-test (roadmap 7).
- Check light, dark and phone width on screen (needs the browser extension). Indicator palette and histogram colours in `chart/utils/model.ts` are still fixed mid-tones.
- Data rights and the paywall (roadmap 1, 2).
