"use client";

import type { UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { IntradayBar } from "../schemas/analysis";
import { minuteToTimestamp } from "../utils/chart-model";

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/** The last price minute by minute, with volume. `day` is the exchange date the minute labels belong to. */
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
      // Minute bars on a thinly traded share are mostly flat single prints, which candles draw as dashes: a stepped line
      // of the last price reads as what it is, a price that holds until the next trade.
      const line = chart.addSeries(lib.LineSeries, { color: css("--brand"), lineWidth: 2, lineType: lib.LineType.WithSteps, pointMarkersVisible: true, pointMarkersRadius: 2, priceLineVisible: true });
      line.priceScale().applyOptions({ scaleMargins: { top: 0.08, bottom: 0.3 } });
      const volume = chart.addSeries(lib.HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "volume", lastValueVisible: false });
      chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.75, bottom: 0 } });
      const t = (b: IntradayBar) => minuteToTimestamp(day, b.time) as UTCTimestamp;
      line.setData(bars.map((b) => ({ time: t(b), value: b.close })));
      volume.setData(bars.map((b) => ({ time: t(b), value: b.volume, color: b.close >= b.open ? up : down })));
      // a little empty space either side, so the first time label is not cut off at the edge
      chart.timeScale().setVisibleLogicalRange({ from: -7, to: bars.length + 2 });
      cleanup = () => chart.remove();
    });
    return () => {
      disposed = true;
      cleanup();
    };
  }, [bars, day]);

  return <div ref={host} className="chart short" role="img" aria-label="Intraday price, minute by minute" data-testid="intraday-chart" />;
}
