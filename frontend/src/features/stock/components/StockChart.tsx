"use client";

import { useCallback, useMemo } from "react";
import { PriceChart, type Annotations, type LiveBar, type Resolution } from "@/features/chart";
import type { Analysis } from "../schemas/analysis";
import { CLEAN, LAYERS, TRADER, useLayers, type Layer } from "../store/chart-prefs";
import { dedupeLines, nearestLevels, patternMarkers, recentPatterns } from "../utils/chart-model";

/** Indicators each layer adds, by timeframe (the same specs the chart's indicator picker uses). */
const SPECS: Record<Extract<Layer, "averages" | "bands" | "rsi" | "macd">, { daily: readonly string[]; intraday: readonly string[] }> = {
  averages: { daily: ["sma(20)", "sma(50)", "sma(200)"], intraday: ["ema(9)", "ema(21)"] },
  bands: { daily: ["bbands(20,2)"], intraday: [] },
  rsi: { daily: ["rsi(14)"], intraday: ["rsi(14)"] },
  macd: { daily: ["macd(12,26,9)"], intraday: [] },
};

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const WATCH = "#7c3aed";
const MAX_PATTERNS = 5;
/** Two lines closer than this share of the price would stack their tags, so the less important one is dropped. */
const MIN_GAP = 0.02;

type Line = NonNullable<Annotations["priceLines"]>[number];

/** The plan and the nearest levels, as annotations for the generic chart. The plan comes first, so where a level and a
 * plan line coincide the plan's tag wins. */
function annotate(a: Analysis, layers: ReadonlySet<Layer>, ctx: { resolution: Resolution; dates: ReadonlySet<string> }): Annotations | undefined {
  if (layers.size === 0) return undefined;
  const up = css("--up");
  const down = css("--dn");
  const zone = css("--decide");
  const story = a.candle_story;
  const lines: Line[] = [];
  let targets = 0;
  const bands: NonNullable<Annotations["bands"]>[number][] = [];
  if (layers.has("plan") && story) {
    for (const x of story.annotations) {
      if (x.kind === "entry") {
        lines.push({ price: x.price, color: zone, title: "Buy zone", style: "solid", width: 2 });
        if (x.price_to != null) bands.push({ from: x.price_to, to: x.price, color: css("--decide-soft") }); // the band shows the lower edge
      } else if (x.kind === "stop") lines.push({ price: x.price, color: down, title: "Stop", style: "dashed", width: 2 });
      else if (x.kind === "target") lines.push({ price: x.price, color: up, title: `Target ${++targets}`, style: "dashed", width: 2 });
      else lines.push({ price: x.price, color: WATCH, title: "Watch", style: "dotted" });
    }
  }
  if (layers.has("levels") && ctx.resolution === "D") {
    for (const l of nearestLevels(a.levels, a.price.ltp ?? a.levels.price)) lines.push({ price: l.price, color: l.kind === "resistance" ? down : up, title: l.title, style: "dotted" });
  }
  const markers: NonNullable<Annotations["markers"]>[number][] = [];
  if (layers.has("patterns") && ctx.resolution === "D") {
    // arrows only: the names are listed under the chart, where they cannot sit on top of candles
    markers.push(...patternMarkers(recentPatterns(a.candles.patterns, ctx.dates, MAX_PATTERNS), { up, down, neutral: "#94a3b8" }, ctx.dates).map((m) => ({ ...m, text: "" })));
  }
  return { priceLines: dedupeLines(lines, MIN_GAP), markers, bands };
}

function note(layers: ReadonlySet<Layer>): string {
  if (layers.size === 0) return "Candles and volume only. Use Layers to add levels, the trade plan, patterns or indicators.";
  const bits = [layers.has("levels") ? "nearest support and resistance" : null, layers.has("plan") ? "buy zone, stop and targets" : null].filter(Boolean);
  return bits.length ? `On the chart: ${bits.join(", ")}.` : "";
}

/** One checkbox per layer, plus two shortcuts. A native <details> keeps it keyboard and screen-reader friendly. */
function LayersMenu({ layers, onChange }: { layers: ReadonlySet<Layer>; onChange: (next: readonly Layer[]) => void }) {
  const toggle = (k: Layer) => onChange(LAYERS.map((l) => l.key).filter((x) => (x === k ? !layers.has(k) : layers.has(x))));
  return (
    <details className="layers">
      <summary className="btn ghost small">Layers{layers.size ? ` (${layers.size})` : ""}</summary>
      <div className="layers-panel" role="group" aria-label="Chart layers">
        <div className="row">
          <button type="button" className="btn ghost small" onClick={() => onChange(CLEAN)}>Clean</button>
          <button type="button" className="btn ghost small" onClick={() => onChange(TRADER)}>Everything</button>
        </div>
        {LAYERS.map((l) => (
          <label key={l.key} title={l.title} className="layer-opt">
            <input type="checkbox" checked={layers.has(l.key)} onChange={() => toggle(l.key)} /> {l.label}
          </label>
        ))}
      </div>
    </details>
  );
}

/** The stock page's chart: the generic chart plus this stock's analysis, one layer at a time. */
export function StockChart({ symbol, analysis, live }: { symbol: string; analysis: Analysis; live: LiveBar | null }) {
  const [layers, setLayers] = useLayers();
  const presets = useCallback(
    (r: Resolution) => (["averages", "bands", "rsi", "macd"] as const).filter((k) => layers.has(k)).flatMap((k) => SPECS[k][r === "D" ? "daily" : "intraday"]),
    [layers],
  );
  const annotations = useCallback((ctx: { resolution: Resolution; dates: ReadonlySet<string>; lastDate: string | null }) => annotate(analysis, layers, ctx), [analysis, layers]);
  const noteFor = useCallback(() => note(layers), [layers]);
  const extras = useMemo(() => <LayersMenu layers={layers} onChange={setLayers} />, [layers, setLayers]);
  const story = analysis.candle_story;
  const showPlan = layers.has("plan") && story;
  const patterns = useMemo(
    () => (layers.has("patterns") ? [...analysis.candles.patterns].sort((a, b) => (a.date < b.date ? 1 : -1)).slice(0, MAX_PATTERNS) : []),
    [layers, analysis.candles.patterns],
  );
  return (
    <div className={showPlan ? "advgrid" : undefined}>
      <div>
        <PriceChart symbol={symbol} scope="stock" presets={presets} annotations={annotations} live={live} toolbarExtras={extras} note={noteFor} />
        {patterns.length ? (
          <p className="small patternlist" aria-label="Recent candle patterns">
            <span className="mute">Recent patterns:</span>{" "}
            {patterns.map((p) => (
              <span key={`${p.date}-${p.pattern}`} className={`ptag ${p.direction === "bullish" ? "up" : p.direction === "bearish" ? "dn" : "mute"}`}>
                {p.direction === "bullish" ? "▲" : p.direction === "bearish" ? "▼" : "●"} {p.pattern} <span className="mute">{p.date.slice(5)}</span>
              </span>
            ))}
          </p>
        ) : null}
      </div>
      {showPlan ? (
        <aside className="advnote" aria-label="Trade plan drawn on the chart" data-agent="trade-plan">
          <p className={`where ${story.where}`}><b>{story.headline}</b></p>
          <ol className="plain small">
            {story.plan.map((p) => (
              <li key={p.step}><b>{p.step}.</b> {p.text}</li>
            ))}
          </ol>
          <ul className="plain small legendkeys">
            <li><i className="sw" style={{ background: "var(--decide)" }} /> Buy zone</li>
            <li><i className="sw" style={{ background: "var(--dn)" }} /> Stop: exit below</li>
            <li><i className="sw" style={{ background: "var(--up)" }} /> Take-profit targets</li>
            <li><i className="sw" style={{ background: WATCH }} /> Watch levels</li>
          </ul>
        </aside>
      ) : null}
    </div>
  );
}
