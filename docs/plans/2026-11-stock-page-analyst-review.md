# Stock page: an analyst's review (Nov 2026)

Reviewed on GP (Grameenphone), a large liquid share, in light mode at 1300 px, every tab, plus the analysis and company
API payloads. Question asked: *if a share analyst had to brief someone on this stock from this page, would the page let
them, and in what order would they want the information?*

## 1. How an analyst reads a share

An analyst answers six questions, in this order, and a good page lets you answer them top to bottom without scrolling past
detail you did not ask for:

1. **What is it and what is happening today?** Name, sector, price, day range, where it sits in its 52-week range, how big
   and how liquid it is.
2. **Is it a good business?** Profitability, debt, earnings trend, dividend record.
3. **Is it cheap?** Price against earnings, book value and dividends; against its own sector; against a fair-value range.
4. **Is now a good time?** Trend, momentum, strength against the market, volume, where price is in its range.
5. **What can go wrong, and what is coming?** Free float and liquidity, debt, falling earnings, volatility; record dates,
   results, AGM, news.
6. **So what would I do?** A plan with an entry zone, a stop and a target, and a plain statement of how good the odds are.

## 2. What the page does today

| Tab | Length | What it leads with |
|-----|-------:|--------------------|
| Overview | 2,344 px | The model's signal (SELL), then chart, then the trade plan, then a "Key facts" table at the very bottom |
| Technicals | 2,279 px | Seven small tables of indicators, a text summary, volume-price labels, an intraday chart |
| Market depth | short | Order book (new) |
| History | long | Price table, seasonality |
| Company | 5,018 px | Fair value table, fundamentals, financial health, profile, 9 years of EPS, statements, shareholding |

Questions 1, 2, 3 and 5 are answered only on the Company tab, below a 5,000 px scroll. The first screen after the price is
the model's output, which is question 6. An analyst would open with 1 and finish with 6.

## 3. Findings, with evidence

### A. The page leads with the conclusion, not the picture
The hero shows price, change, open, high, low, previous close, volume and value. It does not show the 52-week range, market
cap, P/E, dividend yield or whether the market is open. The real "at a glance" facts (P/E 10.4, yield 9.5%, ROE 52.8%, free
float 10%, credit rating AAA) sit in a table at the bottom of Overview and Technicals, and again at the bottom of Company.

### B. The signal card says things a reader will misread
- **"SELL"**: DSE retail investors cannot short. For them SELL means "if you hold it, consider leaving", which is not what
  most readers take from a big red pill on a stock they are thinking of buying.
- **"Hit rate (similar) 62%" next to "Baseline (all days) 62%"** means setups like this one did no better than a random day:
  there is no edge. The card shows both numbers but never says so, and 62% reads as good. "Expectancy +0.02% per trade"
  says the same thing in numbers a beginner will not parse.
- **"Setup score 1/6" and "Risk / reward 0.37"** are shown without a plain statement of what is wrong ("the target is only
  0.9% away and the stop 2.4%").

### C. The same facts are repeated in different words
Signal reasons, the setup checklist, the trade plan, the technical summary and Key facts all restate "price is below the
moving averages" and "RSI is weak". The candle story repeats the full Doji explanation twice. The trade plan table lists
"Watch 228.80" and "Watch 221.90" as two rows that duplicate the target and the support. "Key facts" repeats on every tab.

### D. Numbers that disagree or mislead
| What | Shown | Why it is a problem |
|------|-------|---------------------|
| Dividend yield | 8.34% (Fundamentals), 9.48% (Key facts), 9.5% (Financial health) | Three values for one idea. 9.48% is the last dividend (21.5) over today's price; 8.34% is a different basis. The page never says which |
| Gross margin | 100.0% (Financial health) | The source gives gross profit equal to revenue for GP, so the ratio is meaningless. It should be hidden when the two are equal |
| Fair value | 11 methods from 62.24 (-73%) to 547.50 (+141%) | The table has no conclusion. The backend already computes a median fair value (279.50, +23%) and an implied growth rate, but neither is a headline. P/B and Graham methods do not suit a 52%-ROE telecom, so half the table is noise for this share |
| Quarterly EPS | An empty table with one line of explanation | A whole card with nothing in it |

### E. Context an analyst would insist on is missing
- **Against its sector and the market.** P/E 10.4 means little alone. The data exists: market median P/E 23.4, weighted
  9.3; Telecom median 12.9 (but only 3 companies, so it must be labelled as a small group).
- **Against the index.** GP is down 4.9% in a month. Is the market down too? The chart service already serves DSEX history,
  so relative strength is a small computation. Nothing on the page says whether this is the stock or the market.
- **Ownership and liquidity as risk.** Sponsors hold 90%, free float is 10%, average daily turnover is about Tk 23 mn. That is
  the main practical risk for a small buyer and it is buried in a shareholding table at the bottom of the Company tab.
- **What is coming.** The company payload has 5 events (last dividend 105% interim paid 15 Jul 2026, AGM 20 Apr 2026,
  record date) and news. None of it appears on Overview.
- **The earnings trend at a glance.** EPS fell 19% last year (26.89 to 21.90) and sits in a 9-year table; it deserves a
  sparkline next to the P/E.
- **What changed.** Nothing says what is different from yesterday (new signal, crossed a level, volume spike).

### F. Layout
- Overview is 2,344 px; Company is 5,018 px with five full financial tables. No section says why it matters or what is good.
- Technicals is a grid of seven tables with unlabeled units; the intraday chart is a few dots with a clipped time axis
  (":01") and no explanation.
- Empty or inapplicable cards are shown instead of hidden (Quarterly EPS, "–" cells in the fundamentals table).
- Nothing tells a beginner what a number means or whether it is good ("P/B 5.47", "ATR 2.30", "EPS TTM 21.9").

### G. What works and should stay
The chart, now with layers, levels, drawings and patterns; the trade plan's plain-language steps ("Where to enter, where to
exit"); the fair-value method table as a reference; the financial-health checks with green, amber and red marks; market
depth; the honest "not investment advice" wording.

## 4. Proposed structure

Tabs: **Summary** | **Chart** | **Business** | **Valuation** | **Technicals** | **Market depth** | **History**.

### Summary (new, the default): the analyst's one page
Fits in about one and a half screens and answers the six questions in order.

1. **Header**: name, sector, category, price and change, market status, plus a 52-week range bar with price, buy zone, stop
   and target marked on it; market cap, P/E, yield, free float as small facts beside it.
2. **Verdict line** in plain English, built from the data, for example:
   *"Strong, well-run business paying a high dividend, priced fairly, but in a downtrend. Wait for a pullback to 221.90-224.20."*
3. **Scorecard**, four tiles, each with a rating word, the two or three numbers behind it, and one sentence of meaning:
   - **Business quality**: ROE, net margin, debt/equity, EPS trend (sparkline), dividends paid in how many of 5 years.
   - **Value**: P/E vs sector and market, P/B, yield, fair-value range with its median ("+23% to median").
   - **Timing**: trend vs 50/200-day, RSI, 52-week position, strength vs DSEX over 1M and 3M.
   - **Risk**: free float, average daily turnover, volatility (ATR% of price), debt, falling earnings.
4. **Why**: three reasons for and three against, taken from the existing signal and financial-health checks, each with a
   number. This replaces the current duplicated lists.
5. **Plan**: entry zone, stop, target and risk/reward as a single compact block, with a plain sentence on the odds
   ("Setups like this reached the target first 62% of the time, the same as an average day: no edge today").
6. **Coming up and recent**: record date, AGM, last dividend, results due, latest news and disclosures.
7. **Chart** below the fold, with the layer menu as today.

### Business: question 2 and 5 in depth
Financial health checks, earnings and dividend history as charts (EPS, NAV, dividend per year), profit and loss, balance
sheet and cash flow, shareholding with a plain note on free float, company profile. Each section opens with one sentence
saying what it shows and what is healthy.

### Valuation
One chart of fair-value methods against the price with the median and the middle range marked, a note on which methods
apply to this share (a high-ROE, asset-light company should lean on earnings and dividends, a bank on book value), and the
sector and market comparison.

### Technicals
Keep, but lead with a two-line reading ("Trend down, momentum weak, volume light"), group the tables, label units, and fix
the intraday chart or hide it when there is too little data.

## 5. Where each piece of data comes from

| Item | Have | Compute | Need |
|------|:----:|:-------:|:----:|
| ROE, net margin, debt/equity, EPS and dividend history, shareholding | yes | | |
| 52-week range, market cap, free float, P/E, P/B, yield | yes | | |
| Average turnover, ATR% (volatility) | yes | simple | |
| Fair-value median and range, implied growth | yes | | |
| Sector and market P/E | yes (`/market/pe`) | | |
| Strength vs DSEX | index history served by charts | yes | |
| Events (record date, AGM, dividends) and news | yes (5 events; news varies by share) | | |
| What changed since yesterday | | yes (compare two analyses) | stored snapshot or recompute |
| Verdict sentence and tile ratings | | yes, rules over the above | |
| Peer list with ratios | | partly (sector members from the universe) | a better peer definition than DSE's sector for small groups |

Nothing in the first two phases needs a new data source.

## 6. Language rules
- Say what a number means and whether it is good, next to the number: "ROE 52.8%: very high".
- No raw jargon as a label ("Expectancy / trade", "Baseline (all days)"); say "No better than an average day".
- Replace SELL for a retail audience with plain actions: *Buy zone*, *Wait*, *Avoid for now*, *Consider exiting if you hold*.
- One number for one idea, with its basis named and one place that computes it.
- Hide a card or cell that has no data and say nothing, rather than showing an empty table.

## 7. Build order

| Phase | Work | Size | Data |
|-------|------|------|------|
| A. Fix what is wrong | One dividend-yield number with its basis named; hide gross margin when equal to revenue; drop empty cards and dashes; merge duplicate "Watch" rows; show Key facts once; headline the fair-value median and range; say "no edge" on the signal card | S | none |
| B. Summary tab | Header with 52-week bar and key facts, verdict line, four-tile scorecard, why for and against, compact plan | M | none |
| C. Context | Sector and market P/E, strength vs DSEX, liquidity and free-float risk note, EPS sparkline | M | index history |
| D. Events and news | Coming-up and recent block on Summary | S | none |
| E. Valuation tab | Fair-value chart, which methods apply, comparison | M | none |
| F. What changed | Daily change note | M | a stored previous analysis |
| G. Technicals tidy | Reading line, grouping, intraday fix | S | none |

Phases A and B give the largest improvement for the least risk, and neither touches the backend contract except to add a
few computed fields.

## 8. How we will know it worked
- A first-time reader can say within 30 seconds: what the company does, whether it is good, cheap and well timed, and the
  main risk.
- No number appears twice with different values (a contract test asserts one source for yield, P/E and EPS).
- Overview before the chart is one screen, not two; the Company tab opens with a one-sentence read of each section.
- Back-test the verdict wording the same way the Picks buckets were tested (see `docs/research/picks-backtest-2026-11.md`) before
  it claims anything.

## 9. Decisions needed
1. **Audience.** Beginners (plain words, more explanation) or experienced traders (denser, fewer words)? The plan assumes
   a retail investor who knows basic terms. Say if that is wrong.
2. **Signal wording.** Replace SELL with plain actions as above?
3. **Where the plan lives.** On Summary (recommended) or only under Chart?
4. **Peers.** Telecom has three shares, so its median is weak. Use DSE sectors with a "small group" label, or build a better
   peer set later?

## 10. Progress
**Decisions taken** (audience is everyone): every reading has a plain sentence first and the exact numbers beside it, with
how a rating is reached available on demand; SELL stays as the model's label but is followed by a plain action sentence; the
trade plan goes on the Summary tab.

**Phase A done:**
- one dividend yield on the stock page (last dividend over the price shown, basis named; the exchange's figure only as a fallback);
- gross margin is omitted when gross profit equals revenue (backend);
- the empty Quarterly EPS card and empty fundamentals rows are no longer shown;
- the duplicate "Watch" rows are gone;
- "Key facts and data links" is collapsed (still in the HTML for crawlers and agents);
- fair value opens with its median, the middle half of methods and the full range, and says when the methods disagree;
- the signal card says in words what the action means and whether setups like it had an edge, with the jargon labels replaced.
Pages are 8 to 15% shorter (Overview 2,344 to 2,008 px, Company 5,018 to 4,651 px).

**Phase B done (the Summary, as the top of the Overview tab so the URL, tab name and existing tests keep working):**
- "At a glance": sector, category and market status, a 52-week range bar with the buy zone, stop and target marked, and six
  facts (market value, P/E, dividend yield, free float, typical daily turnover, credit rating).
- "Our reading": the short-term signal pill (captioned) beside one plain sentence and the action it points to.
- Four tiles, Business quality, Value, Timing and Risk, each with a rating word, the numbers behind it, and every rule that
  applied as a sentence with its number (a green tick, red cross or neutral dot). "How these ratings are reached" lists the rules.
- "The case for and against": the three strongest reasons each way; "If you act": buy zone, stop, target, reward per unit
  of risk and the honest sentence about the odds; "Coming up and recent": dividend declared, record date, last AGM, news.
- Then the chart and the full trade plan as before, with the signal's checks and past results in a collapsed section.

**Things worth knowing:**
- The backend has two "buy zones": the trade plan's (from nearby support, drawn on the chart) and the setup plan's tighter
  range around today's price. The page now uses the trade plan's everywhere, and a test pins it. The backend should
  eventually expose one.
- The market median P/E (23.4) is pulled up by small shares; a share only counts as cheap on P/E when it is also at or below
  the size-weighted market P/E (9.3), and both are shown.
- Telecom has 3 companies, so GP is compared with the market, not its sector (needs 5 or more).
- Risk reads High only with three points of risk; one or two flags on a blue chip read Moderate.
- The tile rules are rules of thumb. They have not been back-tested the way the Picks buckets were; the page says so.
- Not yet: strength against the index (phase C), a what-changed note (phase F), the Valuation tab (phase E).

**Phase C done:**
- **Strength against the market.** The share's last month and three months are compared with the DSEX index over the same
  dates (the index read on or before each date). The Timing tile gets a "Vs DSEX, 3 months" fact and one sentence with both
  returns ("Beating the market" or "Lagging the market" at 5 points or more either way, otherwise "Moving with the market").
  It counts one point for or against timing, and the rating note lists it.
- **Earnings trend.** The Business quality tile draws earnings per share for the last eight years as a small line, with the
  first and last year and value written beside it, so a single "EPS fell 19%" has its context.
- Liquidity and free float were already in the Risk tile and the at-a-glance facts.
- Note: the 5-point threshold is a judgement, not a tested cut-off; a share down 7.5% while the index is down 2.9% reads
  "Moving with the market" because the gap is 4.6 points. Revisit if that reads too kind.

**Phase E done (the Valuation tab):**
- **Which methods fit this share.** Each fair-value method is marked Fits, Fits partly or Does not fit, with its reason:
  book-value multiples and the Graham number do not suit a business earning 20% or more on its equity; fixed 15-25x P/E and
  3x book multiples are too rich for banks and financials; higher P/E multiples need growth; earnings methods need positive
  earnings; the dividend method needs a dividend and a record. The headline median now comes from the methods that fit
  (GP: 5 of 11, median 307.27, +35%, against 279.50 and +23% using all), and says how many it used and what it left out.
- **One shared scale.** Every method's fair value is a marker on the same scale with the price as a line, so the spread is
  visible at a glance (hidden on phones, where the mark and the numbers carry it).
- **Against the market.** The share's P/E beside the market median, the size-weighted market P/E and the sector median
  (labelled when the sector has fewer than 5 companies), with a plain note on what each means.
- The Fair value card moved from the Company tab to a new Valuation tab (second tab); the Summary's Value rating uses the
  same fit-based median, so the two always agree.
- The rules are judgement and unit-tested on a high-return company, a bank, a loss-maker, a non-payer and a patchy payer.
  They are not back-tested. Reverse-DCF and the original notes are kept under the table.

**Phase G done (the Technicals tab):**
- **A technical reading first.** One headline ("Trend down, momentum weak, volume light.") and one plain line each for trend,
  momentum, volume, typical daily swing and the nearest support and resistance with their distance from the price.
- **Indicators say what they mean.** The table now has a "What it says" column (for example "Weak: sellers have the upper
  hand", "Above its signal line: momentum improving", "Price is above 0 of the 3 averages", "Inside the bands, 39% of the way up").
- Support and resistance show how far each level is from the price; the repeated text Summary is gone from this tab (it is
  still in the API); the volume-price legend is collapsed under "What these labels mean".
- **Intraday chart fixed.** Minute candles on a thinly traded share were flat dashes. It is now a stepped line of the last
  price with volume, with room at the left edge; with fewer than 8 recorded minutes it says so instead of drawing a dot.
- The reading is built from the same numbers shown below it (pure, unit-tested); thresholds (RSI zones, volume 0.7x and 1.5x,
  the 50 and 200-day averages) are conventional, not back-tested.

**Review status:** A, B, C, E and G are done. Left from the plan: D (more on events and news; the Overview already shows
dividend, record date, AGM and news), F (what changed since yesterday, needs a stored previous analysis).

**Phase F done ("What changed"):**
- **No stored history was needed.** The scanner's row builder already carries the previous bar's values, so the change list
  is computed on request from the same bars: a pure rule set in `analysis/domain/changes.py` and
  `GET /api/v1/stocks/{symbol}/changes`.
- **Rules:** price crossing its 200, 50 or 21-day average; the 9 and 21-day averages crossing; MACD crossing its signal;
  RSI moving into or out of oversold and overbought, or across 50; a new 52-week high, a 20-day breakout or breakdown; a
  move of 4% or more; a gap of 2% or more; volume at 2x its average or more; the volume-price label; a candle pattern on the
  last session. Most important first, at most five, each a plain sentence with its number; when nothing applies the card says
  so ("No notable change...").
- **Where:** a "What changed" card on the Overview, right under the reading. It says "Since the session of <date>".
- The thresholds (4%, 2%, 2x, RSI 30/50/70) are conventional and not back-tested. "Since the previous session" means since
  the last completed bar before today's; it does not compare with an earlier snapshot of this page.

**Review status:** A, B, C, E, F and G are done. Only D (more on events and news) is left, and the Overview already shows
the dividend, record date, AGM and the latest news.
