/** /llms.txt: how an AI agent should read this site (https://llmstxt.org). Plain text, no JavaScript needed. */

const BODY = `# DSE Live Analyzer

> Live quotes, candle analysis with trade plans, company fundamentals and market-wide picks for shares on the
> Dhaka Stock Exchange (DSE). For research only, not investment advice. All JSON is wrapped as {"data", "meta"}.

## Site map
- [Market](/): sectors, movers, P/E, 52-week range.
- [Find shares](/find): Picks (ranked for you), [Custom rules](/find/rules), [All shares table](/find/table).
- [Stock](/stock/GP): one share in depth. [Tools](/tools): return calculator, correlation, CSV download.

## Read one share
- [Stock page](/stock/GP): server-rendered "Key facts" block (<section data-agent="stock-facts">) with
  <div data-field="..."> items and schema.org JSON-LD; works without JavaScript.
- [Analysis JSON](/api/v1/stocks/GP/analysis): price, signal, setup score, trade plan (entry zone, stop, target),
  indicators, candle patterns, support/resistance, valuation, candle_story (plain-language reading of the last
  candles plus chart annotations: kind entry|stop|target|watch with price and label).
- [Brief, Markdown](/api/v1/stocks/GP/brief): the same analysis as compact Markdown for an agent's context.
- [Company JSON](/api/v1/stocks/GP/company): profile, contact, credit rating, capital and loans, EPS/NAV/NOCF
  history, quarterly EPS, dividends, shareholding history, financial statements, director trades, events,
  news, ratios (each with its basis) and health flags. Units are listed in data.units.
- [Chart data](/api/v1/charts/GP?resolution=D&indicators=rsi(14),macd): candles plus indicator series (one
  value per candle) at resolution 1, 5, 30, 60 (minutes) or D; unix UTC. Works for indices (DSEX, DS30, DSES,
  closing values only: "ohlc" is false and indicators needing volume or high/low are skipped with a warning).
- [Indicator catalog](/api/v1/charts/indicators): 88 indicators, their parameters, what they show and what columns
  they need.
- [Daily candles](/api/v1/stocks/GP/candles), [technicals](/api/v1/stocks/GP/technicals).

## Whole market
- [Picks](/api/v1/market/picks?exclude_sectors=Bank,Insurance,Life%20Insurance): every share scored for value
  and entry timing, bucketed buy_zone | wait_pullback | watch | avoid, with reasons. Filters: sectors,
  exclude_sectors, categories, min_value_mn, buckets, min_value_score, limit.
- [Alerts](/api/v1/alerts?symbols=GP,PADMAOIL): buy zone with a bullish candle, stop broken, target hit,
  breakout, bearish candle; each with a stable key.
- [Live quotes](/api/v1/quotes), [market summary](/api/v1/market), [sectors](/api/v1/market/sectors),
  [scanner presets](/api/v1/scanner/presets).

## Reference
- [OpenAPI schema](/api/v1/openapi.json): every endpoint, parameter and response.
`;

export function GET() {
  return new Response(BODY, { headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "public, max-age=3600" } });
}
