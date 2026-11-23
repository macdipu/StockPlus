# Picks score back-test (Nov 2026)

Run: `make backtest ARGS="--step 3"` (a replay of the live scoring, `scanner/application/backtest.py`).
Replayed 42 sessions from 2026-04-23 to 2026-10-26, every third session, 352 shares, 13,520 signals.
Each signal is a share's bucket and scores computed from bars before that day. The outcome is the return from that day's
open to the close 5, 10 and 20 sessions later. "Excess" is the return minus the average share scored that day.
Only equities with at least BDT 1 mn average daily traded value over the previous 20 sessions are included.

## Result by bucket (excess vs the average share that day)

| Bucket | Sessions ahead | Signals | Mean return | Excess | Beat the market |
|--------|---------------:|--------:|------------:|-------:|----------------:|
| Buy zone | 5 | 547 | +0.66% | +1.37% | 58% |
| Buy zone | 10 | 547 | +1.40% | +2.16% | 61% |
| Buy zone | 20 | 542 | +3.91% | +3.19% | 60% |
| Wait for a pullback | 20 | 357 | +3.19% | +0.43% | 42% |
| Watch | 20 | 8,111 | +0.48% | +0.27% | 45% |
| Avoid | 5 | 4,396 | −1.04% | −0.46% | 41% |
| Avoid | 10 | 4,396 | −1.12% | −0.69% | 39% |
| Avoid | 20 | 4,307 | −0.79% | −0.94% | 38% |
| All shares | 20 | 13,317 | +0.28% | 0 | 43% |

Buy zone > Wait > Watch > Avoid in excess return at every horizon, and the gap widens with the horizon.

## Does a higher score mean a higher return? (rank correlation, averaged over days)

| Score | 5 sessions | 10 sessions | 20 sessions | Days with a positive reading (20) |
|-------|-----------:|------------:|------------:|----------------------------------:|
| Pick score | 0.12 | 0.14 | 0.18 | 93% |
| Value score | 0.11 | 0.13 | 0.15 | 93% |
| Entry score | 0.08 | 0.09 | 0.12 | 90% |

The top fifth of shares by entry score returned +1.77% excess over 20 sessions, the bottom fifth −2.02%.
By pick score: top fifth +1.40%, bottom fifth −2.02%.

## What this does and does not show

- **The entry score is the trustworthy part.** It uses only prices known on the day. Its edge is modest but consistent
  (positive on 81–93% of days).
- **The value score and the pick score are flattered.** P/E, EPS, dividend yield and sponsor holding are today's values
  applied to past dates, which a real investor could not have known. Treat their numbers as an upper bound.
- **"Wait for a pullback" does not beat the market** (excess +0.4%, beats it 42% of the time at 20 sessions). The bucket is
  neither a buy nor a sell on this evidence.
- **Small and single-regime.** About one year of history exists, so this is one market period; the market itself fell
  over most windows (average 5-session return −0.4%), which helps shares that fell less. Windows overlap, so the 42 days are
  not independent. No significance test is reported, and none should be implied.
- Survivorship (only currently listed shares), no fees or slippage, entry at the signal day's open.

## What would make it stronger
- Store fundamentals as of each date (the exchange's quarterly and annual filings), then the value score can be tested properly.
- More history, as it accumulates; re-run each quarter and compare.
- Net of fees (about 0.4% per leg) and with a realistic fill price.
- Test the chart-pattern "fit" the same way once enough pattern signals exist.
