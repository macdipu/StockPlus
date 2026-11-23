# Stock chart UX plan (Nov 2026)

Trigger: with Analysis set to Basic or Full the chart is too cluttered to read: the candles are hard to see, and
there is no way to draw on it.

## What is wrong today (from the screenshots and `ChartCanvas.tsx`, `StockChart.tsx`)

| # | Problem | Cause |
|---|---------|-------|
| 1 | Price labels pile up on the right edge and hide the latest candles | Every level is a price line with a boxed title ("R 89.4") AND a boxed axis value (89.40): two labels per line, 3 resistances + 3 supports + zone + stop + targets + watch levels in Full |
| 2 | Pattern names ("Bearish Engulfing", "Doji", "Bullish Marubozu") are printed on the candles, overlap each other, and get cut off at the axis | Every pattern marker carries a text label; there is no cap on how many show |
| 3 | The candles are small | Volume and RSI/MACD panes take the lower third; autoscale includes far-away levels, so the price range is stretched |
| 4 | Basic / Full say nothing about what they turn on | One 3-step switch controls ~10 different things at once |
| 5 | Lines run across the whole chart, so the history is crossed by levels that only matter now | Full-width price lines |
| 6 | No drawing tools | Nothing exists in the chart feature (no trend lines, shapes or measuring) |
| 7 | No chart patterns (triangle, double top, head and shoulders, channel, flag) | Only single/multi-candle patterns are detected |

## Principles

1. The candles come first. Annotations must never cover the last ~30 candles; the default view should look clean.
2. One label per thing. Price lines show a short tag, the axis shows the number once.
3. Show less by default, let people turn on more, one layer at a time, and remember the choice.
4. Detail on demand: pattern names and level explanations appear on hover or in a list, not as permanent text.
5. Drawing is the user's own: stored per stock, easy to undo and delete.

## Plan

### Phase 1: declutter (ship first)
- Replace Off / Basic / Full with **layer chips** that toggle independently: Levels, Trade plan, Patterns, Averages
  (SMA/EMA), Bands, RSI, MACD, Volume. Two shortcuts, **Clean** (candles + volume only) and **Trader** (today's Full).
  Default is Clean + Levels. Choice saved in local storage.
- **Levels:** show only the nearest 2 resistances and 2 supports. One tag per line, number on the axis only. Lines
  start at the last ~40 candles and run right (a series primitive), instead of crossing the full history.
- **Patterns:** markers are small icons only, no text; only the last 10 sessions and only the strongest. Names live in
  a hover card and in a "Recent patterns" list under the chart (click a row to jump to that candle).
- **Trade plan:** one soft band for the buy zone, label inside the band at the left; stop and targets as thin short
  lines with tags; the explanation stays in the side panel (moves below the chart under 1300px).
- **Scale and layout:** annotations are excluded from autoscale (`autoscaleInfoProvider`), so the candles fill the
  view; price pane is at least 65% of the height; volume is shorter; RSI/MACD panes can collapse.
- **Toolbar:** one row: Style, Indicators, Layers (popover with the chips). On phones the layers open in a bottom
  sheet.
- **Done when:** on GP, ENVOYTEX and a thin-volume share, in light and dark, the last 30 candles have no overlap with
  any label at 1300px and 390px (Playwright screenshots before and after, kept in the PR).

### Phase 2: drawing tools
- Left rail: Cursor, Trend line, Ray, Horizontal line, Rectangle, Fibonacci retracement, Measure (price % and bars).
- Built as `lightweight-charts` v5 series primitives (the library's supported way to draw custom shapes that move with
  pan and zoom). Magnet option snaps to open/high/low/close.
- Per stock and per timeframe, saved in the browser first (account storage later, with the existing saved-scans
  pattern). Undo, delete selected, clear all, lock.
- **Done when:** draw, pan, zoom, reload, and the drawings are still on the right candles.

### Phase 3: chart patterns
- Detect from swing highs and lows: ascending/descending/symmetrical triangle, double top/bottom, head and
  shoulders, channel, flag. Drawn as shapes on the chart with a name and a confidence label ("possible"), listed with
  the candle patterns, toggled under Patterns.
- Backend: new pure function in `analysis/domain` with unit tests on fixed price series (like the existing legacy
  parity tests); frontend only draws what it is given. These are heuristics and are labelled as such, not signals.
- **Done when:** known textbook series in the tests are found, and clean trending data produces no patterns.

### Phase 4: polish
- OHLC hover card, keyboard shortcuts for tools, screenshot/export of the chart, touch gestures for drawing.

## Open questions
- "Draw pattern": this plan reads it as drawing tools (Phase 2) plus chart-pattern drawing (Phase 3). Confirm.
- Default layers: Clean + Levels, or Clean only?
