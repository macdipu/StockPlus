import type { IChartApi, ISeriesApi, ISeriesPrimitive, SeriesAttachedParameter, SeriesType, Time } from "lightweight-charts";
import { fibLevels, measureText, segments, type Drawing, type DrawPoint, type XY } from "./drawings";

interface Surface {
  useMediaCoordinateSpace<T>(draw: (scope: { context: CanvasRenderingContext2D; mediaSize: { width: number; height: number } }) => T): T;
}

export interface LayerState {
  drawings: readonly Drawing[];
  selected: string | null;
  /** The shape being drawn: the first point is placed and the second follows the pointer. */
  preview: Drawing | null;
  /** Shapes the app draws itself (chart patterns): painted under the user's drawings, never selectable. */
  shapes: readonly Drawing[];
}

export interface LayerColors {
  line: string;
  fill: string;
  text: string;
  textBackground: string;
}

/** Paints the user's drawings on the price pane. They are stored as candle time + price, so they stay on the same
 * candles while the chart is panned or zoomed. */
export class DrawingsLayer implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null;
  private series: ISeriesApi<SeriesType> | null = null;
  private redraw: (() => void) | null = null;
  private state: LayerState = { drawings: [], selected: null, preview: null, shapes: [] };
  private width = 0;

  constructor(
    private colors: () => LayerColors,
    private barsBetween: (a: DrawPoint, b: DrawPoint) => number,
  ) {}

  attached(p: SeriesAttachedParameter<Time>): void {
    this.chart = p.chart as IChartApi;
    this.series = p.series;
    this.redraw = p.requestUpdate;
  }

  detached(): void {
    this.chart = this.series = this.redraw = null;
  }

  set(next: Partial<LayerState>): void {
    this.state = { ...this.state, ...next };
    this.redraw?.();
  }

  /** A pane point (time + price) to pixels, or null when the time is not on this chart. */
  at = (p: DrawPoint): XY | null => {
    const x = this.chart?.timeScale().timeToCoordinate(p.time as Time);
    const y = this.series?.priceToCoordinate(p.price);
    return x == null || y == null ? null : { x, y };
  };

  paneWidth = (): number => this.width;

  updateAllViews(): void {}

  paneViews() {
    return [
      {
        zOrder: () => "top" as const,
        renderer: () => ({
          draw: (target: Surface) =>
            target.useMediaCoordinateSpace(({ context: c, mediaSize }) => {
              this.width = mediaSize.width;
              const k = this.colors();
              const own = this.state.preview ? [...this.state.drawings, this.state.preview] : this.state.drawings;
              const all = [...this.state.shapes, ...own];
              for (const d of all) this.paint(c, d, k, mediaSize.width, d === this.state.preview, d.id === this.state.selected);
            }),
        }),
      },
    ];
  }

  priceAxisViews() {
    return this.state.drawings
      .filter((d) => d.kind === "hline")
      .map((d) => ({
        coordinate: () => this.at(d.a)?.y ?? -1,
        text: () => d.a.price.toFixed(2),
        textColor: () => "#ffffff",
        backColor: () => d.color ?? this.colors().line,
        visible: () => this.at(d.a) !== null,
        tickVisible: () => true,
      }));
  }

  private paint(c: CanvasRenderingContext2D, d: Drawing, k: LayerColors, width: number, preview: boolean, selected: boolean): void {
    const segs = segments(d, this.at, width);
    if (segs.length === 0) return;
    c.save();
    c.strokeStyle = d.color ?? k.line;
    c.lineWidth = (d.width ?? 2) + (selected ? 1 : 0);
    c.setLineDash(preview || d.dashed ? [5, 4] : []);
    if (d.kind === "rect" && d.b) {
      const a = this.at(d.a);
      const b = this.at(d.b);
      if (a && b) {
        c.fillStyle = k.fill;
        c.fillRect(Math.min(a.x, b.x), Math.min(a.y, b.y), Math.abs(b.x - a.x), Math.abs(b.y - a.y));
      }
    }
    c.beginPath();
    for (const [p, q] of segs) {
      c.moveTo(p.x, p.y);
      c.lineTo(q.x, q.y);
    }
    c.stroke();
    c.setLineDash([]);
    c.font = "11px system-ui, sans-serif";
    c.textBaseline = "middle";
    if (d.kind === "fib" && d.b) {
      const left = Math.min(this.at(d.a)?.x ?? 0, this.at(d.b)?.x ?? 0);
      for (const l of fibLevels(d.a, d.b)) {
        const y = this.series?.priceToCoordinate(l.price);
        if (y == null) continue;
        this.tag(c, `${l.ratio} · ${l.price.toFixed(2)}`, left + 4, y - 9, k);
      }
    }
    if (d.kind === "measure" && d.b) {
      const a = this.at(d.a);
      const b = this.at(d.b);
      if (a && b) this.tag(c, measureText(d.a, d.b, this.barsBetween(d.a, d.b)), (a.x + b.x) / 2 - 60, (a.y + b.y) / 2 - 18, k);
    }
    if (d.dots?.length) {
      c.fillStyle = d.color ?? k.line;
      for (const pt of d.dots) {
        const xy = this.at(pt);
        if (!xy) continue;
        c.beginPath();
        c.arc(xy.x, xy.y, 3.5, 0, Math.PI * 2);
        c.fill();
      }
    }
    if (d.label) {
      const a = this.at(d.a);
      if (a) this.tag(c, d.label, a.x + 6, a.y - 12, k);
    }
    if (selected) {
      c.fillStyle = k.line;
      for (const pt of [d.a, d.b]) {
        const xy = pt ? this.at(pt) : null;
        if (!xy) continue;
        c.beginPath();
        c.arc(xy.x, xy.y, 4, 0, Math.PI * 2);
        c.fill();
      }
    }
    c.restore();
  }

  private tag(c: CanvasRenderingContext2D, text: string, x: number, y: number, k: LayerColors): void {
    const w = c.measureText(text).width + 8;
    c.globalAlpha = 0.9;
    c.fillStyle = k.textBackground;
    c.fillRect(x, y - 7, w, 15);
    c.globalAlpha = 1;
    c.fillStyle = k.text;
    c.fillText(text, x + 4, y + 0.5);
  }
}
