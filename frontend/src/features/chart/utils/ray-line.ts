import type { IChartApi, ISeriesApi, ISeriesPrimitive, SeriesAttachedParameter, SeriesType, Time } from "lightweight-charts";

/** The canvas surface a pane renderer is handed (a small structural slice of the library's own type). */
interface Surface {
  useMediaCoordinateSpace<T>(draw: (scope: { context: CanvasRenderingContext2D; mediaSize: { width: number; height: number } }) => T): T;
}

export interface RayStyle {
  price: number;
  color: string;
  /** A short name drawn at the start of the line ("Support", "Stop"). The number lives on the price axis. */
  tag: string;
  style: "solid" | "dashed" | "dotted";
  width: number;
  /** Fill behind the tag, so it stays readable over candles. */
  tagBackground: string;
  tagColor: string;
}

const DASH = { solid: [], dashed: [6, 4], dotted: [2, 3] } as const;

/**
 * A price level drawn from a given candle to the right edge, instead of across the whole history, with ONE tag at
 * its start and ONE number on the price axis. A built-in price line would repeat the number in a second box and
 * cross every old candle.
 */
export class RayLine implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null;
  private series: ISeriesApi<SeriesType> | null = null;
  private y = -1;
  private x = 0;

  constructor(
    private readonly s: RayStyle,
    private readonly from: Time | undefined,
  ) {}

  attached(p: SeriesAttachedParameter<Time>): void {
    this.chart = p.chart as IChartApi;
    this.series = p.series;
  }

  detached(): void {
    this.chart = null;
    this.series = null;
  }

  updateAllViews(): void {
    const y = this.series?.priceToCoordinate(this.s.price);
    this.y = y ?? -1;
    const x = this.from === undefined ? null : this.chart?.timeScale().timeToCoordinate(this.from);
    this.x = Math.max(0, x ?? 0);
  }

  paneViews() {
    const s = this.s;
    return [
      {
        zOrder: () => "top" as const,
        renderer: () => ({
          draw: (target: Surface) =>
            target.useMediaCoordinateSpace(({ context: c, mediaSize }) => {
              if (this.y < 0 || this.y > mediaSize.height) return;
              c.save();
              c.strokeStyle = s.color;
              c.lineWidth = s.width;
              c.setLineDash([...DASH[s.style]]);
              c.beginPath();
              c.moveTo(this.x, this.y);
              c.lineTo(mediaSize.width, this.y);
              c.stroke();
              if (s.tag) {
                c.setLineDash([]);
                c.font = "11px system-ui, sans-serif";
                const w = c.measureText(s.tag).width + 10;
                const left = Math.min(this.x + 4, mediaSize.width - w - 4);
                c.globalAlpha = 0.9;
                c.fillStyle = s.tagBackground;
                c.fillRect(left, this.y - 17, w, 15);
                c.globalAlpha = 1;
                c.strokeStyle = s.color;
                c.lineWidth = 1;
                c.strokeRect(left + 0.5, this.y - 16.5, w - 1, 14);
                c.fillStyle = s.tagColor;
                c.textBaseline = "middle";
                c.fillText(s.tag, left + 5, this.y - 9.5);
              }
              c.restore();
            }),
        }),
      },
    ];
  }

  priceAxisViews() {
    const s = this.s;
    return [
      {
        coordinate: () => this.y,
        text: () => s.price.toFixed(2),
        textColor: () => "#ffffff",
        backColor: () => s.color,
        visible: () => this.y >= 0,
        tickVisible: () => true,
      },
    ];
  }
}
