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

### Phase 1: declutter (done, except the items under "Left for later")
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

## Phase 1 status
Built: independent layer toggles (Layers menu with Clean / Everything), default candles plus the nearest two
support and resistance; levels and the plan are rays from the last 40 candles with one tag and one axis number
(`chart/utils/ray-line.ts`); lines within 2% of a more important line are dropped; pattern arrows have no text and the
newest five are listed under the chart; moving-average overlays no longer stretch the price scale. Pure helpers
(`nearestLevels`, `dedupeLines`, `recentPatterns`) have unit tests; the e2e test uses the new Layers control.

Since built: collapsible RSI/MACD panels (a Panels row; a shut panel keeps a thin strip and the candles get the room), the
pattern name in the chart legend while the pointer is on its candle, and a "Your drawings" list (select or delete from it).
Left for later: click-to-jump from the pattern list, a bottom sheet for Layers on phones (the dropdown fits at 390px today).

## Phase 2 status
Built: drawing toolbar (Select, Trend line, Ray, Horizontal line, Rectangle, Fibonacci, Measure) with Snap to candle,
Undo and Clear all; drawings are stored as candle time + price per scope, symbol and timeframe in the browser, painted
by one series primitive (`chart/utils/drawings-layer.ts`), so they stay on the same candles when panning and zooming.
Click a drawing with Select and press Delete to remove it; Esc cancels a half-drawn shape. Geometry, hit-testing,
Fibonacci levels, measure text and stored-data validation are pure and unit-tested (`chart/utils/drawings.ts`).
Clicks are read from the chart element, because the library swallows the second of two quick clicks.

Editing: select a drawing, then drag a handle to reshape it or drag the line to move it (a horizontal line moves in
price only); points stay on real candles. Style: with a drawing selected, six colours and 1/2/3 px thickness (kept with the drawing), and a Delete button. The style
row is always present: a row that appears on selection shifted the chart, so the click that followed missed the line and
dropped the selection. Left for later: account storage, a drawings list.
Side fix: the "Notifications" state was decided during render, which made every page log a React hydration error;
it now reads the browser permission through `useSyncExternalStore`.

## Phase 3 status
Built: `analysis/domain/chart_patterns.py` finds swing highs and lows (3 bars either side, swings under 3% ignored)
and, on the last 120 bars, double top/bottom, head and shoulders (and inverse), and triangles, wedges, channels and
ranges fitted to the latest 3 or 4 pivots of each side. Output: name, direction, status (forming or confirmed, by a close
through the neckline or trendline), a 0-100 "fit" (how cleanly the bars match, not a probability), key points and rule
lines. Only patterns that ended within 30 bars show, overlapping duplicates of one kind keep the best, at most 3.
Endpoint `GET /stocks/{symbol}/chart-patterns`. The chart draws a thin zig-zag through the swing points, the rule lines
(dashed while forming, solid once confirmed), dots on the points and a name tag, and lists each pattern with a plain
sentence under the chart. New layer "Chart patterns" (off by default; "Everything" includes it).

Not done: flags and pennants, cup and handle; measured-move targets are stated in the text but not drawn; patterns are
daily only; no back-test of how often these shapes work out (roadmap item 7 covers scoring, not this).
