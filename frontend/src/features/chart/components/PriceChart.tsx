"use client";

import { useCallback, useMemo, useState, type ReactNode } from "react";
import { IndicatorParams, IndicatorPicker, parseSpec, specLabel, useCatalog, type CatalogEntry } from "@/features/indicators";
import { num } from "@/shared/lib/format";
import { ErrorNotice, Loading } from "@/shared/ui/Notice";
import { useChartData } from "../hooks/use-chart-data";
import { RESOLUTIONS, RESOLUTION_LABEL, type Resolution } from "../schemas/chart";
import { useDrawings } from "../store/drawings-store";
import { useChartSpec } from "../store/chart-spec";
import type { Tool } from "../utils/drawings";
import { buildCandles, buildLayers, paletteColor, toChartTime, type Annotations, type LiveBar } from "../utils/model";
import { needsOhlc } from "../utils/styles";
import { ChartCanvas } from "./ChartCanvas";
import { DrawToolbar } from "./DrawToolbar";
import { StylePicker } from "./StylePicker";

/** The API accepts this many indicators per chart. */
const MAX_INDICATORS = 12;
const BASE_HEIGHT = 440;
const PANE_HEIGHT = 120;
/** Where a chart's data comes from, in plain words. */
const SOURCE_NOTE: Record<string, string> = {
  "dse-daily": "",
  "dse-index": "Index values published by the Dhaka Stock Exchange. They are closing values only, so there are no candles or volume.",
  "recorded-ticks": "Intraday candles are built from prices this app recorded from the exchange's live feed. History starts when the app first ran.",
};
const NO_LAYERS = { overlays: [], panes: [], priceLines: [], markers: [], bands: [], shapes: [] };

export interface PriceChartProps {
  symbol: string;
  /** Separates remembered choices: charts with different scopes keep their own style and indicators. */
  scope: string;
  resolutions?: readonly Resolution[];
  defaultResolution?: Resolution;
  /** Indicators the host always wants drawn for a timeframe (spec strings). Pass a stable function (useCallback). */
  presets?: (resolution: Resolution) => readonly string[];
  /**
   * Lines, markers and shaded bands the host adds on top of the price. Pass a stable function (useCallback).
   * `dates` are the trading days on a daily chart (a marker on a day the chart does not have is an error), and
   * `lastDate` is the newest of them; both are empty on intraday charts.
   */
  annotations?: (ctx: { resolution: Resolution; dates: ReadonlySet<string>; lastDate: string | null }) => Annotations | undefined;
  /** Today's live candle, merged into the daily chart. */
  live?: LiveBar | null;
  /** Host controls placed in the toolbar (for example the stock page's analysis level). */
  toolbarExtras?: ReactNode;
  /** A line of text under the toolbar, optionally depending on the timeframe. */
  note?: ReactNode | ((resolution: Resolution) => ReactNode);
}

function lastValue(values: readonly (number | null)[] | undefined): number | null {
  if (!values) return null;
  for (let i = values.length - 1; i >= 0; i--) if (values[i] != null) return values[i] as number;
  return null;
}

/**
 * A price chart for any symbol or index: timeframe tabs, a chart style, and indicators from the catalog with their
 * own settings. Candles and indicator values come from one API call; the host decides nothing about drawing.
 */
export function PriceChart({ symbol, scope, resolutions = RESOLUTIONS, defaultResolution = "D", presets, annotations, live, toolbarExtras, note }: PriceChartProps) {
  const [resolution, setResolution] = useState<Resolution>(resolutions.includes(defaultResolution) ? defaultResolution : (resolutions[0] ?? "D"));
  const [spec, setSpec] = useChartSpec(scope);
  const [picking, setPicking] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [tool, setTool] = useState<Tool>("cursor");
  const [magnet, setMagnet] = useState(false);
  const catalog = useCatalog();

  const presetSpecs = useMemo(() => presets?.(resolution) ?? [], [presets, resolution]);
  const specs = useMemo(() => [...new Set([...presetSpecs, ...spec.indicators])], [presetSpecs, spec.indicators]);
  const userSpecs = spec.indicators.filter((s) => !presetSpecs.includes(s));
  const q = useChartData(symbol, resolution, specs);
  const data = q.data;
  const dataResolution = (data?.resolution ?? resolution) as Resolution; // keep the previous chart's own time scale while a new one loads
  const closesOnly = data ? !data.ohlc : false;
  // An index has closing values only: show an area chart instead of candles without changing what the user chose.
  const style = closesOnly && needsOhlc(spec.style) ? "area" : spec.style;
  const unavailable = useCallback(
    (e: CatalogEntry) => (closesOnly && e.requires.length ? `Needs ${e.requires.join(", ")}, which this series does not have` : null),
    [closesOnly],
  );

  const candles = useMemo(() => (data ? buildCandles(data, dataResolution, live) : []), [data, dataResolution, live]);
  const liveDay = live && live.volume > 0 ? live.day : null;
  const dates = useMemo(() => {
    if (!data || dataResolution !== "D") return new Set<string>();
    const d = new Set(data.candles.time.map((t) => String(toChartTime(t, "D"))));
    if (liveDay) d.add(liveDay);
    return d;
  }, [data, dataResolution, liveDay]);
  const layers = useMemo(() => {
    if (!data) return NO_LAYERS;
    const lastDate = [...dates].sort().at(-1) ?? null;
    return buildLayers({ data, resolution: dataResolution, specs, annotations: annotations?.({ resolution: dataResolution, dates, lastDate }) });
  }, [data, dataResolution, specs, annotations, dates]);
  const [drawings, setDrawings] = useDrawings(`${scope}:${symbol}:${dataResolution}`);
  const entries = useMemo(() => new Map((catalog.data?.indicators ?? []).map((e) => [e.id, e])), [catalog.data]);
  const entryOf = (s: string): CatalogEntry | undefined => entries.get(parseSpec(s)?.id ?? "");

  const add = (s: string) => setSpec({ indicators: spec.indicators.includes(s) ? spec.indicators : [...spec.indicators, s] });
  const remove = (s: string) => setSpec({ indicators: spec.indicators.filter((x) => x !== s) });
  const replace = (from: string, to: string) => {
    setSpec({ indicators: [...new Set(spec.indicators.map((x) => (x === from ? to : x)))] });
    setEditing(null);
  };

  return (
    <div data-agent="chart" data-symbol={symbol}>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
        <div className="seg" role="tablist" aria-label="Timeframe">
          {resolutions.map((r) => (
            <button key={r} type="button" role="tab" aria-selected={resolution === r} className={resolution === r ? "on" : ""} onClick={() => setResolution(r)}>
              {RESOLUTION_LABEL[r]}
            </button>
          ))}
        </div>
        <div className="chartopts">
          <StylePicker value={style} onChange={(next) => setSpec({ style: next })} closesOnly={closesOnly} />
          <button type="button" className="btn ghost small" onClick={() => setPicking(true)} aria-haspopup="dialog">
            Indicators{userSpecs.length ? ` (${userSpecs.length})` : ""}
          </button>
          {toolbarExtras}
        </div>
      </div>
      {note ? <p className="small mute" style={{ margin: "0 0 8px" }}>{typeof note === "function" ? note(resolution) : note}</p> : null}

      {userSpecs.length ? (
        <div className="ind-chips" aria-label="Indicators on the chart">
          {userSpecs.map((s) => {
            const entry = entryOf(s);
            const series = data?.indicators.find((i) => i.key === s);
            const v = entry && series ? lastValue(series.series[entry.outputs[0]?.key ?? ""]) : null;
            return (
              <span key={s} className="ind-chip" data-indicator={s}>
                <i className="swatch" style={{ background: paletteColor(Math.max(0, specs.indexOf(s))) }} aria-hidden="true" />
                {entry ? specLabel(entry, s) : s}
                {v != null ? <span className="mute num">&nbsp;{num(v, Math.abs(v) < 10 ? 3 : 2)}</span> : null}
                {entry && entry.params.length ? <button type="button" aria-label={`Settings for ${entry.name}`} onClick={() => setEditing(editing === s ? null : s)}>Settings</button> : null}
                <button type="button" aria-label={`Remove ${entry?.name ?? s}`} onClick={() => remove(s)}>✕</button>
              </span>
            );
          })}
        </div>
      ) : null}
      {editing && entryOf(editing) ? (
        <IndicatorParams entry={entryOf(editing) as CatalogEntry} spec={editing} onApply={(next) => replace(editing, next)} onCancel={() => setEditing(null)} />
      ) : null}
      {data ? <p className="small mute" style={{ margin: "0 0 6px" }}>{SOURCE_NOTE[data.source] ?? ""}</p> : null}
      {data && data.warnings.length ? <p className="small dn" role="status" style={{ margin: "0 0 6px" }}>{data.warnings.join(". ")}.</p> : null}

      {data ? (
        <DrawToolbar tool={tool} onTool={setTool} magnet={magnet} onMagnet={setMagnet} count={drawings.length} canDelete={drawings.length > 0} onUndo={() => setDrawings(drawings.slice(0, -1))} onClear={() => setDrawings([])} />
      ) : null}
      {q.isPending ? <Loading what="Loading chart" /> : null}
      {q.isError && !data ? <ErrorNotice error={q.error} /> : null}
      {data ? (
        <ChartCanvas
          key={`${dataResolution}-${style}`}
          candles={candles}
          layers={layers}
          style={style}
          height={BASE_HEIGHT + PANE_HEIGHT * layers.panes.length}
          label={`${symbol} ${RESOLUTION_LABEL[dataResolution]} chart`}
          tool={tool}
          magnet={magnet}
          drawings={drawings}
          onDrawings={setDrawings}
        />
      ) : null}

      {picking ? <IndicatorPicker active={userSpecs} limit={MAX_INDICATORS - presetSpecs.length} onAdd={add} onClose={() => setPicking(false)} unavailable={unavailable} /> : null}
    </div>
  );
}

