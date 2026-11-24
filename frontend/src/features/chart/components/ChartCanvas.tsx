"use client";

import type * as LightweightCharts from "lightweight-charts";
import type { IChartApi, ISeriesApi, SeriesType } from "lightweight-charts";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { num } from "@/shared/lib/format";
import type { Candle, Layers } from "../utils/model";
import { DrawingsLayer } from "../utils/drawings-layer";
import { dragDrawing, hitTest, newId, pointsNeeded, snapPrice, type Drawing, type DragMode, type DrawKind, type DrawPoint, type Tool } from "../utils/drawings";
import { paneHeight } from "../utils/layout";
import { RayLine } from "../utils/ray-line";
import { baselineValue, toHeikinAshi, type ChartStyle } from "../utils/styles";

type Lib = typeof LightweightCharts;
const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
/** Levels are drawn from this many candles back, so they never cross the older history. */
const RAY_BARS = 40;

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
  /** What a click does: select a drawing, or place one of the drawing tools. */
  tool: Tool;
  magnet: boolean;
  drawings: readonly Drawing[];
  onDrawings: (next: readonly Drawing[]) => void;
  /** The selected drawing changed (null when nothing is selected). */
  onSelect: (id: string | null) => void;
  /** Selection made outside the chart (the drawings list). */
  selectedId: string | null;
  /** Keys of indicator panels shown as a thin strip. */
  collapsed: ReadonlySet<string>;
}

/** Draws candles, indicator lines and panels, annotations and shaded bands. Pure drawing: it fetches nothing. */
export function ChartCanvas({ candles, layers, style, label, height, tool, magnet, drawings, onDrawings, onSelect, selectedId, collapsed }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const bandHost = useRef<HTMLDivElement>(null);
  const api = useRef<{ drawCandles: (c: readonly Candle[]) => void; drawLayers: (l: Layers) => void; sync: () => void; cancel: () => void; deleteSelected: () => void; select: (id: string | null) => void; heights: () => void } | null>(null);
  const latest = useRef({ candles, layers });
  const draw = useRef({ tool, magnet, drawings, onDrawings });
  const shapes = useRef<readonly Drawing[]>(layers.shapes);
  const collapsedRef = useRef(collapsed);
  const markerLabels = useRef<ReadonlyMap<string, readonly string[]>>(new Map());
  const report = useRef(onSelect);
  useEffect(() => {
    report.current = onSelect;
  });
  const [legend, setLegend] = useState("");
  const [note, setNote] = useState<{ x: number; y: number; point: DrawPoint } | null>(null); // a note being typed
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
      main.series.priceScale().applyOptions({ scaleMargins: { top: 0.06, bottom: 0.2 } });
      const volume = chart.addSeries(lib.HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "volume", lastValueVisible: false, priceLineVisible: false });
      chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.86, bottom: 0 } });
      const markers = lib.createSeriesMarkers(main.series, []);
      let extra: Array<ISeriesApi<SeriesType>> = [];
      let rays: RayLine[] = [];
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
        // a series with no volume (an index) draws no volume bars at all
        volume.setData(cs.some((b) => b.volume > 0) ? cs.map((b) => ({ time: b.time, value: b.volume, color: b.close >= b.open ? `${k.up}88` : `${k.down}88` })) : []);
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
          const s = chart.addSeries(lib.LineSeries, { autoscaleInfoProvider: () => null, color: o.color, lineWidth: 1, lineVisible: o.kind !== "dots", pointMarkersVisible: o.kind === "dots", priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
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
          chart.panes()[i + 1]?.setHeight(paneHeight(collapsedRef.current.has(pane.key)));
        });
        for (const r of rays) main.series.detachPrimitive(r);
        const from = latest.current.candles[Math.max(0, latest.current.candles.length - RAY_BARS)]?.time;
        rays = l.priceLines.map((p) => new RayLine({ price: p.price, color: p.color, tag: p.title, style: p.style, width: p.width ?? 1, tagBackground: css("--card"), tagColor: css("--ink") }, from));
        for (const r of rays) main.series.attachPrimitive(r);
        const labels = new Map<string, string[]>();
        for (const m of l.markers) if (m.label) labels.set(String(m.time), [...(labels.get(String(m.time)) ?? []), m.label]);
        markerLabels.current = labels;
        markers.setMarkers(l.markers.map(({ label: _label, ...m }) => m).sort((a, b) => (String(a.time) < String(b.time) ? -1 : String(a.time) > String(b.time) ? 1 : 0)));
        requestAnimationFrame(() => drawBands(l));
      };

      chart.subscribeCrosshairMove((p) => {
        const d = p.seriesData.get(main.series) as { open?: number; high?: number; low?: number; close?: number; value?: number } | undefined;
        if (!d) return setLegend("");
        if (d.value != null) return setLegend(`Close ${num(d.value)}`);
        if (d.close == null) return setLegend("");
        const tags = markerLabels.current.get(String(p.time));
        setLegend(`O ${num(d.open)}  H ${num(d.high)}  L ${num(d.low)}  C ${num(d.close)}${tags ? `  ·  ${tags.join(", ")}` : ""}`);
      });
      chart.timeScale().subscribeVisibleLogicalRangeChange(() => drawBands(latest.current.layers));

      // ---- the user's drawings: placed by clicks, painted by one primitive, kept as candle time + price
      const indexOf = (p: DrawPoint) => latest.current.candles.findIndex((c) => String(c.time) === String(p.time));
      const layer = new DrawingsLayer(
        () => ({ line: "#6d7cff", fill: "rgba(109,124,255,0.12)", text: css("--ink"), textBackground: css("--card"), up: css("--up"), down: css("--dn") }),
        (a, b) => Math.abs(indexOf(b) - indexOf(a)),
        () => chart.timeScale().options().barSpacing,
      );
      main.series.attachPrimitive(layer);
      let pendingPts: DrawPoint[] = []; // the clicks so far of a drawing that needs more than one
      let preview: Drawing | null = null;
      let selected: string | null = null;
      let override: Drawing | null = null; // the drawing being dragged, until the mouse is released
      const current = () => (override ? draw.current.drawings.map((d) => (d.id === override?.id ? override : d)) : draw.current.drawings);
      let reported: string | null = null;
      const sync = () => {
        if (selected && !current().some((d) => d.id === selected)) selected = null; // it was deleted elsewhere
        layer.set({ drawings: current(), selected, preview, shapes: shapes.current });
        if (selected !== reported) {
          reported = selected;
          report.current(selected);
        }
      };
      // The library swallows the second of two quick clicks (it reads them as a double-click), so clicks are read from
      // the element itself. A drag (pan) is not a click. The point snaps to the candle under the pointer.
      const pointAt = (x: number, y: number): DrawPoint | null => {
        const logical = chart.timeScale().coordinateToLogical(x);
        const price = main.series.coordinateToPrice(y);
        const candle = logical == null ? undefined : latest.current.candles[Math.round(logical)];
        if (!candle || price == null) return null; // the empty space after the last candle has no time
        return { time: candle.time as string | number, price: draw.current.magnet ? snapPrice(price, candle) : price };
      };
      const local = (e: MouseEvent) => {
        const r = (host.current as HTMLDivElement).getBoundingClientRect();
        return { x: e.clientX - r.left, y: e.clientY - r.top };
      };
      let down: { x: number; y: number } | null = null;
      const onDown = (e: MouseEvent) => {
        down = { x: e.clientX, y: e.clientY };
      };
      const onClick = (e: MouseEvent) => {
        if (down && Math.hypot(e.clientX - down.x, e.clientY - down.y) > 4) return; // a drag
        const { tool: t, drawings: list, onDrawings: commit } = draw.current;
        const at = local(e);
        if (t === "cursor") {
          selected = hitTest(list, at, layer.at, layer.paneWidth(), 7, layer.view());
          sync();
          return;
        }
        const here = pointAt(at.x, at.y);
        if (!here) return;
        if (t === "text") {
          setNote({ x: at.x, y: at.y, point: here }); // the words are typed into a box at the click
          return;
        }
        const need = pointsNeeded(t);
        if (need === 1) return commit([...list, { id: newId(), kind: t, a: here }]);
        pendingPts.push(here);
        if (pendingPts.length < need) return;
        commit([...list, build(t, pendingPts)]);
        pendingPts = [];
        preview = null;
        sync();
      };
      /** A finished or half-finished drawing from its clicks. A position's stop and target sit under its entry's date. */
      const build = (kind: DrawKind, pts: readonly DrawPoint[], id = newId()): Drawing => {
        const [a, b, c] = pts as [DrawPoint, DrawPoint | undefined, DrawPoint | undefined];
        const under = (p: DrawPoint | undefined) => (p ? { time: a.time, price: p.price } : undefined);
        const position = kind === "long" || kind === "short";
        const second = position ? under(b) : b;
        const third = position ? under(c) : c;
        return { id, kind, a, ...(second ? { b: second } : {}), ...(third ? { c: third } : {}) };
      };
      // ---- edit: drag a selected drawing's handle to reshape it, or its line to move it. Runs first (capture) and
      // stops the event so the chart does not also pan.
      let drag: { mode: DragMode; from: DrawPoint; orig: Drawing } | null = null;
      const onDragMove = (e: MouseEvent) => {
        if (!drag) return;
        const at = local(e);
        const here = pointAt(at.x, at.y);
        if (!here) return;
        override = dragDrawing(drag.orig, drag.mode, drag.from, here, latest.current.candles.map((c) => c.time as string | number));
        sync();
      };
      const onDragEnd = () => {
        window.removeEventListener("mousemove", onDragMove);
        window.removeEventListener("mouseup", onDragEnd);
        const done = override;
        drag = null;
        if (done) draw.current.onDrawings(current());
        override = null;
        sync();
      };
      const onDragStart = (e: MouseEvent) => {
        if (draw.current.tool !== "cursor" || e.button !== 0) return;
        const at = local(e);
        const list = draw.current.drawings;
        let target = list.find((d) => d.id === selected);
        let mode: DragMode | null = null;
        for (const m of ["a", "b", "c"] as const) {
          const pt = target?.[m];
          const xy = pt ? layer.at(pt) : null;
          if (xy && Math.hypot(xy.x - at.x, xy.y - at.y) <= 9) mode = m;
        }
        if (!mode) {
          const hit = hitTest(list, at, layer.at, layer.paneWidth(), 7, layer.view());
          if (!hit) return;
          selected = hit;
          target = list.find((d) => d.id === hit);
          mode = "move";
          sync();
        }
        const from = pointAt(at.x, at.y);
        if (!target || !from) return;
        drag = { mode, from, orig: target };
        down = { x: e.clientX, y: e.clientY }; // the click that follows a drag is not a click
        e.stopPropagation();
        window.addEventListener("mousemove", onDragMove);
        window.addEventListener("mouseup", onDragEnd);
      };
      const el = host.current;
      el.addEventListener("mousedown", onDragStart, true);
      el.addEventListener("mousedown", onDown);
      el.addEventListener("click", onClick);
      chart.subscribeCrosshairMove((p) => {
        const t = draw.current.tool;
        if (pendingPts.length === 0 || t === "cursor" || t === "text" || !p.point) return;
        const here = pointAt(p.point.x, p.point.y);
        if (!here) return;
        preview = build(t, [...pendingPts, here], "preview");
        sync();
      });
      const cancel = () => {
        pendingPts = [];
        preview = null;
        sync();
      };
      const deleteSelected = () => {
        if (!selected) return;
        const gone = selected;
        selected = null;
        draw.current.onDrawings(draw.current.drawings.filter((d) => d.id !== gone));
      };

      const select = (id: string | null) => {
        if (selected === id) return;
        selected = id;
        sync();
      };
      const heights = () => latest.current.layers.panes.forEach((pane, i) => chart.panes()[i + 1]?.setHeight(paneHeight(collapsedRef.current.has(pane.key))));
      api.current = { drawCandles, drawLayers, sync, cancel, deleteSelected, select, heights };
      sync();
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
        el.removeEventListener("mousedown", onDragStart, true);
        window.removeEventListener("mousemove", onDragMove);
        window.removeEventListener("mouseup", onDragEnd);
        el.removeEventListener("mousedown", onDown);
        el.removeEventListener("click", onClick);
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
    shapes.current = layers.shapes;
    api.current?.sync();
  }, [layers]);
  useEffect(() => {
    draw.current = { tool, magnet, drawings, onDrawings };
    api.current?.sync();
  }, [tool, magnet, drawings, onDrawings]);
  useEffect(() => {
    api.current?.cancel(); // switching tools abandons a half-drawn shape
  }, [tool]);
  useEffect(() => {
    api.current?.select(selectedId);
  }, [selectedId]);
  useEffect(() => {
    collapsedRef.current = collapsed;
    api.current?.heights();
  }, [collapsed]);

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") api.current?.cancel();
    else if (e.key === "Delete" || e.key === "Backspace") api.current?.deleteSelected();
  };

  return (
    <div className="chartwrap" style={{ height }} tabIndex={0} onKeyDown={onKeyDown} role="group" aria-label={`${label}: click to select a drawing, Delete removes it`}>
      <div ref={host} className="chartbox" role="img" aria-label={label} data-testid="price-chart" />
      <div ref={bandHost} className="bands" aria-hidden="true" />
      {note && tool === "text" ? (
        <input
          className="inp noteinput"
          style={{ left: note.x, top: Math.max(0, note.y - 30) }}
          autoFocus
          maxLength={120}
          placeholder="Type a note, press Enter"
          aria-label="Note text"
          onKeyDown={(e) => {
            e.stopPropagation();
            if (e.key === "Escape") setNote(null);
            if (e.key === "Enter" && e.currentTarget.value.trim()) {
              draw.current.onDrawings([...draw.current.drawings, { id: newId(), kind: "text", a: note.point, text: e.currentTarget.value.trim() }]);
              setNote(null);
            }
          }}
          onBlur={() => setNote(null)}
        />
      ) : null}
      {legend ? <div className="chartlegend small num">{legend}</div> : null}
    </div>
  );
}
