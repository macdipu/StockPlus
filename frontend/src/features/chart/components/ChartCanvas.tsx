"use client";

import type * as LightweightCharts from "lightweight-charts";
import type { IChartApi, ISeriesApi, SeriesType } from "lightweight-charts";
import { useEffect, useRef, useState } from "react";
import { num } from "@/shared/lib/format";
import type { Candle, Layers } from "../utils/model";
import { baselineValue, toHeikinAshi, type ChartStyle } from "../utils/styles";

type Lib = typeof LightweightCharts;
const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const SUBPANE_HEIGHT = 110;

function colors() {
  return { up: css("--up"), down: css("--dn"), accent: css("--brand"), mute: css("--mute"), ink: css("--ink"), line: css("--line") };
}

function themeOptions(lib: Lib) {
  const c = colors();
  return {
    layout: { background: { type: lib.ColorType.Solid, color: "transparent" }, textColor: c.ink, panes: { separatorColor: c.line } },
    grid: { vertLines: { color: c.line }, horzLines: { color: c.line } },
    rightPriceScale: { borderColor: c.line },
    timeScale: { borderColor: c.line },
  };
}

interface Main {
  series: ISeriesApi<SeriesType>;
  set: (candles: readonly Candle[]) => void;
}

const ohlc = (cs: readonly Candle[]) => cs.map(({ time, open, high, low, close }) => ({ time, open, high, low, close }));
const closes = (cs: readonly Candle[]) => cs.map((b) => ({ time: b.time, value: b.close }));

/** The price series for a chart style. Every style draws from the same candles. */
function createMain(lib: Lib, chart: IChartApi, style: ChartStyle): Main {
  const k = colors();
  switch (style) {
    case "bars":
    case "hlc_bars": {
      const s = chart.addSeries(lib.BarSeries, { upColor: k.up, downColor: k.down, openVisible: style === "bars" });
      return { series: s, set: (cs) => { const c = colors(); s.applyOptions({ upColor: c.up, downColor: c.down }); s.setData(ohlc(cs)); } };
    }
    case "line":
    case "line_markers":
    case "step": {
      const s = chart.addSeries(lib.LineSeries, { color: k.accent, lineWidth: 2, lineType: style === "step" ? lib.LineType.WithSteps : lib.LineType.Simple, pointMarkersVisible: style === "line_markers" });
      return { series: s, set: (cs) => { s.applyOptions({ color: colors().accent }); s.setData(closes(cs)); } };
    }
    case "area":
    case "hlc_area": {
      const s = chart.addSeries(lib.AreaSeries, { lineColor: k.accent, topColor: `${k.accent}55`, bottomColor: `${k.accent}05`, lineWidth: 2 });
      const hi = style === "hlc_area" ? chart.addSeries(lib.LineSeries, { color: k.up, lineWidth: 1, lineStyle: lib.LineStyle.Dotted, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }) : null;
      const lo = style === "hlc_area" ? chart.addSeries(lib.LineSeries, { color: k.down, lineWidth: 1, lineStyle: lib.LineStyle.Dotted, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }) : null;
      return {
        series: s,
        set: (cs) => {
          const c = colors();
          s.applyOptions({ lineColor: c.accent, topColor: `${c.accent}55`, bottomColor: `${c.accent}05` });
          s.setData(closes(cs));
          hi?.applyOptions({ color: c.up });
          lo?.applyOptions({ color: c.down });
          hi?.setData(cs.map((b) => ({ time: b.time, value: b.high })));
          lo?.setData(cs.map((b) => ({ time: b.time, value: b.low })));
        },
      };
    }
    case "baseline": {
      const s = chart.addSeries(lib.BaselineSeries, { lineWidth: 2 });
      return {
        series: s,
        set: (cs) => {
          const c = colors();
          s.applyOptions({
            baseValue: { type: "price", price: baselineValue(cs.map((b) => b.close)) },
            topLineColor: c.up, topFillColor1: `${c.up}55`, topFillColor2: `${c.up}08`,
            bottomLineColor: c.down, bottomFillColor1: `${c.down}08`, bottomFillColor2: `${c.down}55`,
          });
          s.setData(closes(cs));
        },
      };
    }
    case "columns": {
      const s = chart.addSeries(lib.HistogramSeries, { priceFormat: { type: "price", precision: 2, minMove: 0.01 } });
      return {
        series: s,
        set: (cs) => {
          const c = colors();
          const floor = cs.length ? Math.min(...cs.map((b) => b.low)) * 0.98 : 0; // columns grow from just under the lowest price
          s.applyOptions({ base: floor });
          s.setData(cs.map((b) => ({ time: b.time, value: b.close, color: b.close >= b.open ? c.up : c.down })));
        },
      };
    }
    case "high_low": {
      const s = chart.addSeries(lib.CandlestickSeries, { upColor: k.accent, downColor: k.accent, borderVisible: false, wickVisible: false });
      return { series: s, set: (cs) => { const c = colors(); s.applyOptions({ upColor: c.accent, downColor: c.accent }); s.setData(cs.map((b) => ({ time: b.time, open: b.low, high: b.high, low: b.low, close: b.high }))); } };
    }
    default: {
      // candles, hollow candles, Heikin Ashi
      const s = chart.addSeries(lib.CandlestickSeries, {});
      return {
        series: s,
        set: (cs) => {
          const c = colors();
          s.applyOptions({
            upColor: style === "hollow" ? "rgba(0,0,0,0)" : c.up,
            downColor: c.down,
            borderVisible: style === "hollow",
            borderUpColor: c.up,
            borderDownColor: c.down,
            wickUpColor: c.up,
            wickDownColor: c.down,
          });
          s.setData(ohlc(style === "heikin" ? toHeikinAshi(cs) : cs));
        },
      };
    }
  }
}

interface Props {
  candles: readonly Candle[];
  layers: Layers;
  style: ChartStyle;
  label: string;
  height: number;
}

/** Draws candles, indicator lines and panels, annotations and shaded bands. Pure drawing: it fetches nothing. */
export function ChartCanvas({ candles, layers, style, label, height }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const bandHost = useRef<HTMLDivElement>(null);
  const api = useRef<{ drawCandles: (c: readonly Candle[]) => void; drawLayers: (l: Layers) => void } | null>(null);
  const latest = useRef({ candles, layers });
  const [legend, setLegend] = useState("");
  useEffect(() => {
    latest.current = { candles, layers };
  });

  useEffect(() => {
    let disposed = false;
    let cleanup = () => {};
    void import("lightweight-charts").then((lib) => {
      if (disposed || !host.current) return;
      const chart = lib.createChart(host.current, { autoSize: true, ...themeOptions(lib), timeScale: { timeVisible: true, secondsVisible: false, borderColor: css("--line") } });
      const main = createMain(lib, chart, style);
      main.series.priceScale().applyOptions({ scaleMargins: { top: 0.06, bottom: 0.24 } });
      const volume = chart.addSeries(lib.HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "volume", lastValueVisible: false, priceLineVisible: false });
      chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
      const markers = lib.createSeriesMarkers(main.series, []);
      const STYLE = { solid: lib.LineStyle.Solid, dashed: lib.LineStyle.Dashed, dotted: lib.LineStyle.Dotted };
      let extra: Array<ISeriesApi<SeriesType>> = [];
      let lines: Array<ReturnType<typeof main.series.createPriceLine>> = [];
      let drawn = 0;

      const drawBands = (l: Layers) => {
        const el = bandHost.current;
        if (!el) return;
        el.innerHTML = "";
        for (const b of l.bands) {
          const y1 = main.series.priceToCoordinate(b.to);
          const y2 = main.series.priceToCoordinate(b.from);
          if (y1 == null || y2 == null) continue;
          const div = document.createElement("div");
          div.className = "band";
          div.style.top = `${Math.min(y1, y2)}px`;
          div.style.height = `${Math.max(2, Math.abs(y2 - y1))}px`;
          div.style.background = b.color;
          el.appendChild(div);
        }
      };

      const drawCandles = (cs: readonly Candle[]) => {
        const k = colors();
        main.set(cs);
        volume.setData(cs.map((b) => ({ time: b.time, value: b.volume, color: b.close >= b.open ? `${k.up}88` : `${k.down}88` })));
        // History can arrive after the chart exists (first only today's live candle is known): zoom to the latest
        // ~120 candles whenever a whole batch arrives. One new live candle keeps the viewport where it is.
        if (cs.length - drawn > 1) chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, cs.length - 120), to: cs.length + 4 });
        drawn = cs.length;
      };

      const drawLayers = (l: Layers) => {
        const k = colors();
        for (const s of extra) chart.removeSeries(s);
        extra = [];
        for (const o of l.overlays) {
          const s = chart.addSeries(lib.LineSeries, { color: o.color, lineWidth: 1, lineVisible: o.kind !== "dots", pointMarkersVisible: o.kind === "dots", priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
          s.setData(o.points);
          extra.push(s);
        }
        l.panes.forEach((pane, i) => {
          const made: Array<ISeriesApi<SeriesType>> = [];
          pane.series.forEach((sp, j) => {
            const paneOptions = { priceLineVisible: false, lastValueVisible: j === 0, title: j === 0 ? pane.title : "", ...(pane.scale ? { autoscaleInfoProvider: () => ({ priceRange: { minValue: pane.scale![0], maxValue: pane.scale![1] } }) } : {}) };
            let s: ISeriesApi<SeriesType>;
            if (sp.kind === "histogram") {
              s = chart.addSeries(lib.HistogramSeries, paneOptions, i + 1);
              (s as ISeriesApi<"Histogram">).setData(sp.points.map((p) => ({ time: p.time, value: p.value, color: p.color })));
            } else if (sp.kind === "area") {
              s = chart.addSeries(lib.AreaSeries, { ...paneOptions, lineColor: sp.color, topColor: `${sp.color}55`, bottomColor: `${sp.color}05`, lineWidth: 1 }, i + 1);
              (s as ISeriesApi<"Area">).setData(sp.points.map((p) => ({ time: p.time, value: p.value })));
            } else {
              s = chart.addSeries(lib.LineSeries, { ...paneOptions, color: sp.color, lineWidth: 1, lineVisible: sp.kind !== "dots", pointMarkersVisible: sp.kind === "dots", crosshairMarkerVisible: false }, i + 1);
              (s as ISeriesApi<"Line">).setData(sp.points.map((p) => ({ time: p.time, value: p.value })));
            }
            extra.push(s);
            made.push(s);
          });
          for (const level of pane.levels) made[0]?.createPriceLine({ price: level, color: k.mute, lineWidth: 1, lineStyle: lib.LineStyle.Dotted, axisLabelVisible: false, title: "" });
          chart.panes()[i + 1]?.setHeight(SUBPANE_HEIGHT);
        });
        for (const pl of lines) main.series.removePriceLine(pl);
        lines = l.priceLines.map((p) => main.series.createPriceLine({ price: p.price, color: p.color, lineWidth: p.width ?? 1, lineStyle: STYLE[p.style], axisLabelVisible: true, title: p.title }));
        markers.setMarkers([...l.markers].sort((a, b) => (String(a.time) < String(b.time) ? -1 : String(a.time) > String(b.time) ? 1 : 0)));
        requestAnimationFrame(() => drawBands(l));
      };

      chart.subscribeCrosshairMove((p) => {
        const d = p.seriesData.get(main.series) as { open?: number; high?: number; low?: number; close?: number; value?: number } | undefined;
        if (!d) return setLegend("");
        if (d.value != null) return setLegend(`Close ${num(d.value)}`);
        if (d.close == null) return setLegend("");
        setLegend(`O ${num(d.open)}  H ${num(d.high)}  L ${num(d.low)}  C ${num(d.close)}`);
      });
      chart.timeScale().subscribeVisibleLogicalRangeChange(() => drawBands(latest.current.layers));

      api.current = { drawCandles, drawLayers };
      drawCandles(latest.current.candles);
      drawLayers(latest.current.layers);

      const scheme = window.matchMedia("(prefers-color-scheme: dark)");
      const onScheme = () => {
        chart.applyOptions(themeOptions(lib));
        drawCandles(latest.current.candles);
        drawLayers(latest.current.layers);
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
  }, [style]); // a new style builds a new chart (the parent also re-keys this component)

  useEffect(() => {
    api.current?.drawCandles(candles);
  }, [candles]);
  useEffect(() => {
    api.current?.drawLayers(layers);
  }, [layers]);

  return (
    <div className="chartwrap" style={{ height }}>
      <div ref={host} className="chartbox" role="img" aria-label={label} data-testid="price-chart" />
      <div ref={bandHost} className="bands" aria-hidden="true" />
      {legend ? <div className="chartlegend small num">{legend}</div> : null}
    </div>
  );
}
