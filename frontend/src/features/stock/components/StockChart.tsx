"use client";

import { useCallback, useMemo } from "react";
import { PriceChart, type Annotations, type LiveBar, type Resolution } from "@/features/chart";
import type { Analysis } from "../schemas/analysis";
import { ANALYSIS_LEVELS, useAnalysisLevel, type AnalysisLevel } from "../store/chart-prefs";
import { levelLines, patternMarkers } from "../utils/chart-model";

/** Indicators each analysis level draws, by timeframe (the same specs the chart's indicator picker uses). */
const PRESETS: Record<Exclude<AnalysisLevel, "off">, { daily: readonly string[]; intraday: readonly string[] }> = {
  basic: { daily: ["sma(20)", "sma(50)", "sma(200)", "ema(9)", "ema(21)"], intraday: ["ema(9)", "ema(21)"] },
  full: { daily: ["sma(20)", "sma(50)", "sma(200)", "ema(21)", "bbands(20,2)", "rsi(14)", "macd(12,26,9)"], intraday: ["ema(9)", "ema(21)", "rsi(14)"] },
};

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const ZONE = "#d97706";
const WATCH = "#7c3aed";

/** The trade plan and support/resistance, as annotations for the generic chart. */
function annotate(a: Analysis, level: AnalysisLevel, ctx: { resolution: Resolution; dates: ReadonlySet<string>; lastDate: string | null }): Annotations | undefined {
  if (level === "off") return undefined;
  const up = css("--up");
  const down = css("--dn");
  const story = a.candle_story;
  const out: { priceLines: NonNullable<Annotations["priceLines"]>; markers: NonNullable<Annotations["markers"]>; bands: NonNullable<Annotations["bands"]> } = { priceLines: [], markers: [], bands: [] };
  const priceLines = out.priceLines as Array<NonNullable<Annotations["priceLines"]>[number]>;
  const bands = out.bands as Array<NonNullable<Annotations["bands"]>[number]>;
  const markers = out.markers as Array<NonNullable<Annotations["markers"]>[number]>;
  if (level === "full" && story) {
    for (const x of story.annotations) {
      if (x.kind === "entry") {
        priceLines.push({ price: x.price, color: ZONE, title: x.label, style: "solid", width: 2 });
        if (x.price_to != null) {
          priceLines.push({ price: x.price_to, color: ZONE, title: "", style: "solid", width: 2 });
          bands.push({ from: x.price_to, to: x.price, color: "rgba(217,119,6,0.13)" });
        }
      } else if (x.kind === "stop") priceLines.push({ price: x.price, color: down, title: x.label, style: "solid", width: 2 });
      else if (x.kind === "target") priceLines.push({ price: x.price, color: up, title: x.label, style: "dashed", width: 2 });
      else priceLines.push({ price: x.price, color: WATCH, title: x.label, style: "dotted" });
    }
  } else if (ctx.resolution === "D") {
    for (const l of levelLines(a.levels)) priceLines.push({ price: l.price, color: l.kind === "resistance" ? down : up, title: l.title, style: "dashed" });
  }
  if (ctx.resolution === "D") {
    markers.push(...patternMarkers(a.candles.patterns, { up, down, neutral: "#94a3b8" }, ctx.dates));
    if (level === "full" && story && ctx.lastDate) {
      const text = { inside_buy_zone: "IN BUY ZONE", above_buy_zone: "ABOVE ZONE: wait", below_buy_zone: "BELOW ZONE: wait", below_stop: "BELOW STOP: exit" }[story.where];
      markers.push({ time: ctx.lastDate, position: "aboveBar", shape: "circle", color: story.where === "inside_buy_zone" ? ZONE : story.where === "below_stop" ? down : css("--mute"), text });
    }
  }
  return out;
}

function note(level: AnalysisLevel, resolution: Resolution): string {
  if (level === "off") return "Prices and volume only.";
  if (resolution !== "D") return `Times in Dhaka (UTC+6). EMA 9 / 21${level === "full" ? ", RSI and the plan levels" : ""}.`;
  return level === "full" ? "Buy zone shaded, stop, targets, watch levels, patterns, Bollinger bands, RSI, MACD." : "SMA 20/50/200, EMA 9/21, support and resistance, candle patterns.";
}

/** The stock page's chart: the generic chart plus this stock's analysis drawn on it at the chosen level. */
export function StockChart({ symbol, analysis, live }: { symbol: string; analysis: Analysis; live: LiveBar | null }) {
  const [level, setLevel] = useAnalysisLevel();
  const presets = useCallback((r: Resolution) => (level === "off" ? [] : PRESETS[level][r === "D" ? "daily" : "intraday"]), [level]);
  const annotations = useCallback((ctx: { resolution: Resolution; dates: ReadonlySet<string>; lastDate: string | null }) => annotate(analysis, level, ctx), [analysis, level]);
  const noteFor = useCallback((r: Resolution) => note(level, r), [level]);
  const extras = useMemo(
    () => (
      <div className="seg" role="group" aria-label="Analysis on the chart">
        <span className="seg-label small mute">Analysis</span>
        {ANALYSIS_LEVELS.map((l) => (
          <button key={l.key} type="button" aria-pressed={level === l.key} title={l.title} className={level === l.key ? "on" : ""} onClick={() => setLevel(l.key)}>
            {l.label}
          </button>
        ))}
      </div>
    ),
    [level, setLevel],
  );
  const story = analysis.candle_story;
  const showPlan = level === "full" && story;
  return (
    <div className={showPlan ? "advgrid" : undefined}>
      <PriceChart symbol={symbol} scope="stock" presets={presets} annotations={annotations} live={live} toolbarExtras={extras} note={noteFor} />
      {showPlan ? (
        <aside className="advnote" aria-label="Trade plan drawn on the chart" data-agent="trade-plan">
          <p className={`where ${story.where}`}><b>{story.headline}</b></p>
          <ol className="plain small">
            {story.plan.map((p) => (
              <li key={p.step}><b>{p.step}.</b> {p.text}</li>
            ))}
          </ol>
          <ul className="plain small legendkeys">
            <li><i className="sw" style={{ background: ZONE }} /> Buy zone</li>
            <li><i className="sw" style={{ background: "var(--dn)" }} /> Stop: exit below</li>
            <li><i className="sw" style={{ background: "var(--up)" }} /> Take-profit targets</li>
            <li><i className="sw" style={{ background: WATCH }} /> Watch levels</li>
          </ul>
        </aside>
      ) : null}
    </div>
  );
}
