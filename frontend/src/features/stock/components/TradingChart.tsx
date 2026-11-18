"use client";

import type * as LightweightCharts from "lightweight-charts";
import type { IChartApi, Time, UTCTimestamp } from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";
import { useBars } from "@/features/company";
import { num } from "@/shared/lib/format";
import { ErrorNotice, Loading } from "@/shared/ui/Notice";
import type { Analysis, TechnicalBar } from "../schemas/analysis";
import { OVERLAYS, levelLines, patternMarkers, toCandles, toLine, toVolume } from "../utils/chart-model";
import { ema, macd, rsi } from "../utils/indicators";

type Lib = typeof LightweightCharts;
type Tab = "1" | "5" | "30" | "60" | "D" | "ADV";

const TABS: ReadonlyArray<{ key: Tab; label: string; title: string }> = [
  { key: "1", label: "1min", title: "1-minute candles, last two sessions" },
  { key: "5", label: "5min", title: "5-minute candles" },
  { key: "30", label: "30min", title: "30-minute candles" },
  { key: "60", label: "1h", title: "1-hour candles" },
  { key: "D", label: "D", title: "Daily candles with moving averages, support and resistance" },
  { key: "ADV", label: "Advanced", title: "Daily candles with the full analysis drawn on: buy zone, stop, targets, watch levels, patterns, Bollinger bands, RSI and MACD" },
];
const DHAKA_OFFSET_S = 6 * 3600; // the chart shows times as UTC; shift so the axis reads Dhaka time

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

interface Candle {
  time: Time;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface PriceLineSpec {
  price: number;
  color: string;
  title: string;
  style: "solid" | "dashed" | "dotted";
  width?: 1 | 2;
}

interface Model {
  candles: Candle[];
  overlays: Array<{ key: string; color: string; points: Array<{ time: Time; value: number }>; width?: 1 | 2; dashed?: boolean }>;
  priceLines: PriceLineSpec[];
  markers: Array<{ time: Time; position: "aboveBar" | "belowBar"; shape: "arrowUp" | "arrowDown" | "circle"; color: string; text: string }>;
  bands: Array<{ from: number; to: number; color: string }>;
  panes: boolean; // RSI + MACD panes below the price
}

function themeOptions(lib: Lib) {
  return {
    layout: { background: { type: lib.ColorType.Solid, color: "transparent" }, textColor: css("--ink"), panes: { separatorColor: css("--line") } },
    grid: { vertLines: { color: css("--line") }, horzLines: { color: css("--line") } },
    rightPriceScale: { borderColor: css("--line") },
    timeScale: { borderColor: css("--line") },
  };
}

function colors() {
  return { up: css("--up"), down: css("--dn"), accent: css("--accent"), mute: css("--mute"), zone: "#d97706", watch: "#7c3aed" };
}

// ------------------------------------------------------------------------------------------ models
function intradayModel(bars: ReadonlyArray<{ time: number; open: number; high: number; low: number; close: number; volume: number }>, a: Analysis): Model {
  const c = colors();
  const candles: Candle[] = bars.map((b) => ({ ...b, time: (b.time + DHAKA_OFFSET_S) as UTCTimestamp }));
  const closes = candles.map((b) => b.close);
  const line = (vals: (number | null)[]) => candles.flatMap((b, i) => (vals[i] == null ? [] : [{ time: b.time, value: vals[i]! }]));
  const plan = a.candle_story?.annotations ?? [];
  const lo = Math.min(...candles.map((b) => b.low));
  const hi = Math.max(...candles.map((b) => b.high));
  const span = hi - lo || hi * 0.02;
  const near = (p: number) => p > lo - span * 0.6 && p < hi + span * 0.6; // only levels within sight of the candles
  return {
    candles,
    overlays: [
      { key: "EMA 9", color: "#06b6d4", points: line(ema(closes, 9)) },
      { key: "EMA 21", color: "#ec4899", points: line(ema(closes, 21)) },
    ],
    priceLines: plan
      .filter((x) => near(x.price))
      .map((x) => ({
        price: x.price,
        color: x.kind === "stop" ? c.down : x.kind === "target" ? c.up : x.kind === "entry" ? c.zone : c.watch,
        title: x.label,
        style: "dashed" as const,
      })),
    markers: [],
    bands: [],
    panes: false,
  };
}

function dailyModel(bars: readonly TechnicalBar[], a: Analysis, advanced: boolean): Model {
  const c = colors();
  const vols = toVolume(bars, c.up, c.down);
  const volBy = new Map(vols.map((v) => [v.time, v.value]));
  const candles: Candle[] = toCandles(bars).map((b) => ({ ...b, time: b.time as Time, volume: volBy.get(b.time) ?? 0 }));
  const known = new Set(bars.map((b) => b.date));
  const overlays: Model["overlays"] = OVERLAYS.filter((o) => !advanced || o.key !== "ema9")
    .map((o) => ({ key: o.label, color: o.color, points: toLine(bars, o.key).map((p) => ({ time: p.time as Time, value: p.value })) }));
  if (advanced) {
    for (const k of ["bb_upper", "bb_lower"] as const) {
      overlays.push({
        key: k === "bb_upper" ? "BB upper" : "BB lower",
        color: "#94a3b8",
        dashed: true,
        points: bars.flatMap((b) => (b[k] == null ? [] : [{ time: b.date as Time, value: b[k]! }])),
      });
    }
  }
  const story = a.candle_story;
  const priceLines: PriceLineSpec[] = [];
  const bands: Model["bands"] = [];
  if (advanced && story) {
    for (const x of story.annotations) {
      if (x.kind === "entry") {
        priceLines.push({ price: x.price, color: c.zone, title: x.label, style: "solid", width: 2 });
        if (x.price_to != null) {
          priceLines.push({ price: x.price_to, color: c.zone, title: "", style: "solid", width: 2 });
          bands.push({ from: x.price_to, to: x.price, color: "rgba(217,119,6,0.13)" });
        }
      } else if (x.kind === "stop") priceLines.push({ price: x.price, color: c.down, title: x.label, style: "solid", width: 2 });
      else if (x.kind === "target") priceLines.push({ price: x.price, color: c.up, title: x.label, style: "dashed", width: 2 });
      else priceLines.push({ price: x.price, color: c.watch, title: x.label, style: "dotted" });
    }
  } else {
    for (const l of levelLines(a.levels)) {
      priceLines.push({ price: l.price, color: l.kind === "resistance" ? c.down : c.up, title: l.title, style: "dashed" });
    }
  }
  const markers = patternMarkers(a.candles.patterns, { ...c, neutral: "#94a3b8" }, known).map((m) => ({ ...m, time: m.time as Time }));
  if (advanced && story) {
    // label the latest candle with where the price stands
    const last = candles.at(-1);
    const where = { inside_buy_zone: "IN BUY ZONE", above_buy_zone: "ABOVE ZONE: wait", below_buy_zone: "BELOW ZONE: wait", below_stop: "BELOW STOP: exit" }[story.where];
    if (last) markers.push({ time: last.time, position: "aboveBar", shape: "circle", color: story.where === "inside_buy_zone" ? c.zone : story.where === "below_stop" ? c.down : c.mute, text: where });
    markers.sort((x, y) => (String(x.time) < String(y.time) ? -1 : String(x.time) > String(y.time) ? 1 : 0));
  }
  return { candles, overlays, priceLines, markers, bands, panes: advanced };
}

// ------------------------------------------------------------------------------------------ canvas
function ChartCanvas({ model, height, label }: { model: Model; height: number; label: string }) {
  const host = useRef<HTMLDivElement>(null);
  const bandHost = useRef<HTMLDivElement>(null);
  const api = useRef<{ chart: IChartApi; draw: (m: Model) => void } | null>(null);
  const latest = useRef(model);
  const [legend, setLegend] = useState<string>("");
  useEffect(() => {
    latest.current = model;
  });

  useEffect(() => {
    let disposed = false;
    let cleanup = () => {};
    void import("lightweight-charts").then((lib) => {
      if (disposed || !host.current) return;
      const chart = lib.createChart(host.current, { autoSize: true, ...themeOptions(lib), timeScale: { timeVisible: true, secondsVisible: false, borderColor: css("--line") } });
      const c = colors();
      const candle = chart.addSeries(lib.CandlestickSeries, { upColor: c.up, downColor: c.down, borderVisible: false, wickUpColor: c.up, wickDownColor: c.down });
      candle.priceScale().applyOptions({ scaleMargins: { top: 0.06, bottom: 0.24 } });
      const volume = chart.addSeries(lib.HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "volume", lastValueVisible: false, priceLineVisible: false });
      chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
      const markers = lib.createSeriesMarkers(candle, []);
      let overlays: Array<ReturnType<typeof chart.addSeries>> = [];
      let lines: Array<ReturnType<typeof candle.createPriceLine>> = [];
      let paneSeries: Array<ReturnType<typeof chart.addSeries>> = [];
      const STYLE = { solid: lib.LineStyle.Solid, dashed: lib.LineStyle.Dashed, dotted: lib.LineStyle.Dotted };

      const drawBands = (m: Model) => {
        const el = bandHost.current;
        if (!el) return;
        el.innerHTML = "";
        for (const b of m.bands) {
          const y1 = candle.priceToCoordinate(b.to);
          const y2 = candle.priceToCoordinate(b.from);
          if (y1 == null || y2 == null) continue;
          const div = document.createElement("div");
          div.className = "band";
          div.style.top = `${Math.min(y1, y2)}px`;
          div.style.height = `${Math.max(2, Math.abs(y2 - y1))}px`;
          div.style.background = b.color;
          el.appendChild(div);
        }
      };

      const draw = (m: Model) => {
        const k = colors();
        candle.applyOptions({ upColor: k.up, downColor: k.down, wickUpColor: k.up, wickDownColor: k.down });
        candle.setData(m.candles.map(({ volume: _v, ...b }) => b));
        volume.setData(m.candles.map((b) => ({ time: b.time, value: b.volume, color: b.close >= b.open ? `${k.up}88` : `${k.down}88` })));
        for (const s of overlays) chart.removeSeries(s);
        overlays = m.overlays.map((o) => {
          const s = chart.addSeries(lib.LineSeries, { color: o.color, lineWidth: o.width ?? 1, lineStyle: o.dashed ? lib.LineStyle.Dashed : lib.LineStyle.Solid, priceLineVisible: false, lastValueVisible: false, title: o.key, crosshairMarkerVisible: false });
          s.setData(o.points);
          return s;
        });
        for (const l of lines) candle.removePriceLine(l);
        lines = m.priceLines.map((l) => candle.createPriceLine({ price: l.price, color: l.color, lineWidth: l.width ?? 1, lineStyle: STYLE[l.style], axisLabelVisible: true, title: l.title }));
        markers.setMarkers(m.markers);
        for (const s of paneSeries) chart.removeSeries(s);
        paneSeries = [];
        if (m.panes && m.candles.length > 30) {
          const closes = m.candles.map((b) => b.close);
          const r = rsi(closes);
          const md = macd(closes);
          const rs = chart.addSeries(lib.LineSeries, { color: "#7c3aed", lineWidth: 1, priceLineVisible: false, title: "RSI 14" }, 1);
          rs.setData(m.candles.flatMap((b, i) => (r[i] == null ? [] : [{ time: b.time, value: r[i]! }])));
          rs.createPriceLine({ price: 70, color: k.down, lineWidth: 1, lineStyle: lib.LineStyle.Dotted, axisLabelVisible: false, title: "overbought 70" });
          rs.createPriceLine({ price: 30, color: k.up, lineWidth: 1, lineStyle: lib.LineStyle.Dotted, axisLabelVisible: false, title: "oversold 30" });
          const hist = chart.addSeries(lib.HistogramSeries, { priceLineVisible: false, lastValueVisible: false, title: "MACD hist" }, 2);
          hist.setData(m.candles.flatMap((b, i) => (md[i]?.hist == null ? [] : [{ time: b.time, value: md[i]!.hist!, color: md[i]!.hist! >= 0 ? `${k.up}aa` : `${k.down}aa` }])));
          const ml = chart.addSeries(lib.LineSeries, { color: "#2563eb", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: "MACD" }, 2);
          ml.setData(m.candles.flatMap((b, i) => (md[i]?.macd == null ? [] : [{ time: b.time, value: md[i]!.macd! }])));
          const sl = chart.addSeries(lib.LineSeries, { color: "#f59e0b", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: "signal" }, 2);
          sl.setData(m.candles.flatMap((b, i) => (md[i]?.signal == null ? [] : [{ time: b.time, value: md[i]!.signal! }])));
          paneSeries = [rs, hist, ml, sl];
          const panes = chart.panes();
          panes[1]?.setHeight(90);
          panes[2]?.setHeight(90);
        }
        requestAnimationFrame(() => drawBands(m));
      };

      chart.subscribeCrosshairMove((p) => {
        const d = p.seriesData.get(candle) as { open?: number; high?: number; low?: number; close?: number } | undefined;
        if (!d || d.close == null) return setLegend("");
        setLegend(`O ${num(d.open)}  H ${num(d.high)}  L ${num(d.low)}  C ${num(d.close)}`);
      });
      chart.timeScale().subscribeVisibleLogicalRangeChange(() => drawBands(latest.current));

      api.current = { chart, draw };
      draw(latest.current);
      const n = latest.current.candles.length;
      chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, n - 120), to: n + 4 });

      const scheme = window.matchMedia("(prefers-color-scheme: dark)");
      const onScheme = () => {
        chart.applyOptions(themeOptions(lib));
        draw(latest.current);
      };
      scheme.addEventListener("change", onScheme);
      cleanup = () => {
        scheme.removeEventListener("change", onScheme);
        chart.remove();
        api.current = null;
      };
    });
    return () => {
      disposed = true;
      cleanup();
    };
  }, []);

  useEffect(() => {
    api.current?.draw(model);
  }, [model]);

  return (
    <div className="chartwrap" style={{ height }}>
      <div ref={host} className="chartbox" role="img" aria-label={label} data-testid="price-chart" />
      <div ref={bandHost} className="bands" aria-hidden="true" />
      {legend ? <div className="chartlegend small num">{legend}</div> : null}
    </div>
  );
}

// ------------------------------------------------------------------------------------------ public
interface Props {
  symbol: string;
  bars: readonly TechnicalBar[];
  analysis: Analysis;
}

/** Price chart with timeframe tabs. "Advanced" draws the whole analysis on the daily chart. */
export function TradingChart({ symbol, bars, analysis }: Props) {
  const [tab, setTab] = useState<Tab>("D");
  const intraday = tab !== "D" && tab !== "ADV";
  const q = useBars(symbol, intraday ? (tab as "1" | "5" | "30" | "60") : "5", intraday);
  const model = useMemo(() => {
    if (intraday) return q.data && q.data.length ? intradayModel(q.data, analysis) : null;
    return dailyModel(bars, analysis, tab === "ADV");
  }, [intraday, q.data, bars, analysis, tab]);
  const story = analysis.candle_story;
  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="seg" role="tablist" aria-label="Timeframe">
          {TABS.map((t) => (
            <button key={t.key} type="button" role="tab" aria-selected={tab === t.key} title={t.title} className={tab === t.key ? "on" : ""} onClick={() => setTab(t.key)}>
              {t.label}
            </button>
          ))}
        </div>
        <span className="small mute">{intraday ? "Times in Dhaka (UTC+6). EMA 9 / 21, plan levels in view." : tab === "ADV" ? "Buy zone shaded, stop, targets, watch levels, patterns, Bollinger bands, RSI, MACD." : "SMA 20/50/200, EMA 9/21, support and resistance, candle patterns."}</span>
      </div>
      {intraday && q.isPending ? <Loading what="Loading candles" /> : null}
      {intraday && q.isError ? <ErrorNotice error={q.error} /> : null}
      {model ? (
        <div className={tab === "ADV" ? "advgrid" : undefined}>
          <ChartCanvas key={tab} model={model} height={tab === "ADV" ? 640 : 520} label={`${symbol} ${TABS.find((t) => t.key === tab)?.title ?? ""}`} />
          {tab === "ADV" && story ? (
            <aside className="advnote" aria-label="Trade plan drawn on the chart" data-agent="trade-plan">
              <p className={`where ${story.where}`}><b>{story.headline}</b></p>
              <ol className="plain small">
                {story.plan.map((p) => (
                  <li key={p.step}><b>{p.step}.</b> {p.text}</li>
                ))}
              </ol>
              <ul className="plain small legendkeys">
                <li><i className="sw" style={{ background: "#d97706" }} /> Buy zone</li>
                <li><i className="sw" style={{ background: "var(--dn)" }} /> Stop: exit below</li>
                <li><i className="sw" style={{ background: "var(--up)" }} /> Take-profit targets</li>
                <li><i className="sw" style={{ background: "#7c3aed" }} /> Watch levels</li>
              </ul>
            </aside>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
