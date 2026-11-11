"use client";

import type * as LightweightCharts from "lightweight-charts";
import type { IChartApi } from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { Analysis, TechnicalBar } from "../schemas/analysis";
import {
  OVERLAYS,
  levelLines,
  patternMarkers,
  toCandles,
  toLine,
  toVolume,
} from "../utils/chart-model";

interface Props {
  bars: readonly TechnicalBar[];
  patterns: Analysis["candles"]["patterns"];
  levels: Analysis["levels"];
}

type Chart = IChartApi;
type Lib = typeof LightweightCharts;

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function themeOptions(lib: Lib) {
  return {
    layout: { background: { type: lib.ColorType.Solid, color: "transparent" }, textColor: css("--ink") },
    grid: { vertLines: { color: css("--line") }, horzLines: { color: css("--line") } },
    rightPriceScale: { borderColor: css("--line") },
    timeScale: { borderColor: css("--line") },
  };
}

/** Candles + moving averages + volume + support/resistance + candle-pattern markers. */
export function PriceChart({ bars, patterns, levels }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const handle = useRef<{ chart: Chart; lib: Lib; draw: (p: Props) => void } | null>(null);
  const latest = useRef<Props>({ bars, patterns, levels });
  useEffect(() => {
    latest.current = { bars, patterns, levels }; // read by the theme-change handler below
  });

  // Create the chart once; tear it down on unmount.
  useEffect(() => {
    let disposed = false;
    let cleanup = () => {};
    void import("lightweight-charts").then((lib) => {
      if (disposed || !host.current) return;
      const chart = lib.createChart(host.current, { autoSize: true, ...themeOptions(lib) });
      const colors = () => ({ up: css("--up"), down: css("--dn") });
      const candle = chart.addSeries(lib.CandlestickSeries, {
        upColor: colors().up, downColor: colors().down, borderVisible: false, wickUpColor: colors().up, wickDownColor: colors().down,
      });
      candle.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: 0.28 } });
      const volume = chart.addSeries(lib.HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "volume", lastValueVisible: false, priceLineVisible: false });
      chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.78, bottom: 0 } });
      const lines = OVERLAYS.map((o) => ({
        key: o.key,
        series: chart.addSeries(lib.LineSeries, { color: o.color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: o.label, crosshairMarkerVisible: false }),
      }));
      const markers = lib.createSeriesMarkers(candle, []);
      let priceLines: ReturnType<typeof candle.createPriceLine>[] = [];

      const draw = (p: Props) => {
        const c = colors();
        candle.applyOptions({ upColor: c.up, downColor: c.down, wickUpColor: c.up, wickDownColor: c.down });
        candle.setData(toCandles(p.bars));
        volume.setData(toVolume(p.bars, c.up, c.down));
        for (const l of lines) l.series.setData(toLine(p.bars, l.key));
        markers.setMarkers(patternMarkers(p.patterns, { ...c, neutral: "#94a3b8" }, new Set(p.bars.map((b) => b.date))));
        for (const pl of priceLines) candle.removePriceLine(pl);
        priceLines = levelLines(p.levels).map((l) =>
          candle.createPriceLine({ price: l.price, color: l.kind === "resistance" ? c.down : c.up, lineWidth: 1, lineStyle: lib.LineStyle.Dashed, axisLabelVisible: true, title: l.title }),
        );
      };

      handle.current = { chart, lib, draw };
      draw(latest.current);
      chart.timeScale().fitContent();

      const scheme = window.matchMedia("(prefers-color-scheme: dark)");
      const onScheme = () => {
        chart.applyOptions(themeOptions(lib));
        draw(latest.current);
      };
      scheme.addEventListener("change", onScheme);
      cleanup = () => {
        scheme.removeEventListener("change", onScheme);
        chart.remove();
        handle.current = null;
      };
    });
    return () => {
      disposed = true;
      cleanup();
    };
  }, []);

  // New data (including the live bar) redraws without recreating the chart or moving the viewport.
  useEffect(() => {
    handle.current?.draw({ bars, patterns, levels });
  }, [bars, patterns, levels]);

  return <div ref={host} className="chart" role="img" aria-label="Price chart with moving averages and volume" data-testid="price-chart" />;
}
