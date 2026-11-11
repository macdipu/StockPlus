"use client";

import type { UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { IntradayBar } from "../schemas/analysis";
import { minuteToTimestamp } from "../utils/chart-model";

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/** 1-minute candles with volume. `day` is the exchange date the minute labels belong to. */
export function IntradayChart({ bars, day }: { bars: readonly IntradayBar[]; day: string }) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let disposed = false;
    let cleanup = () => {};
    void import("lightweight-charts").then((lib) => {
      if (disposed || !host.current) return;
      const up = css("--up");
      const down = css("--dn");
      const chart = lib.createChart(host.current, {
        autoSize: true,
        layout: { background: { type: lib.ColorType.Solid, color: "transparent" }, textColor: css("--ink") },
        grid: { vertLines: { color: css("--line") }, horzLines: { color: css("--line") } },
        timeScale: { timeVisible: true, secondsVisible: false, borderColor: css("--line") },
        rightPriceScale: { borderColor: css("--line") },
      });
      const candle = chart.addSeries(lib.CandlestickSeries, { upColor: up, downColor: down, borderVisible: false, wickUpColor: up, wickDownColor: down });
      candle.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: 0.3 } });
      const volume = chart.addSeries(lib.HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "volume", lastValueVisible: false });
      chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.75, bottom: 0 } });
      const t = (b: IntradayBar) => minuteToTimestamp(day, b.time) as UTCTimestamp;
      candle.setData(bars.map((b) => ({ time: t(b), open: b.open, high: b.high, low: b.low, close: b.close })));
      volume.setData(bars.map((b) => ({ time: t(b), value: b.volume, color: b.close >= b.open ? up : down })));
      chart.timeScale().fitContent();
      cleanup = () => chart.remove();
    });
    return () => {
      disposed = true;
      cleanup();
    };
  }, [bars, day]);

  return <div ref={host} className="chart short" role="img" aria-label="Intraday one-minute chart" data-testid="intraday-chart" />;
}
