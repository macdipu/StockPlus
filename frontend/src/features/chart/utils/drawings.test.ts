import { describe, expect, it } from "vitest";
import type { Segment } from "./drawings";
import { channelOffset, describeDrawing, dragDrawing, distanceToSegment, pointsNeeded, positionStats, fibLevels, hitTest, measureText, parseDrawings, segments, snapPrice, type Drawing, type DrawPoint } from "./drawings";

const p = (time: string, price: number): DrawPoint => ({ time, price });
// a fake screen: x = day number * 10, y = 200 - price
const at = (q: DrawPoint) => ({ x: Number(String(q.time).slice(-2)) * 10, y: 200 - q.price });

describe("parseDrawings", () => {
  it("keeps valid drawings and drops anything unexpected", () => {
    const good = { id: "a", kind: "trend", a: p("2026-01-01", 1), b: p("2026-01-02", 2) };
    const out = parseDrawings([good, { id: "b", kind: "trend", a: p("x", 1) }, { id: "c", kind: "weird", a: p("x", 1) }, null, "s", { id: "d", kind: "hline", a: p("2026-01-03", 5) }]);
    expect(out.map((d) => d.id)).toEqual(["a", "d"]);
    expect(parseDrawings("nope")).toEqual([]);
  });
});

describe("fibLevels", () => {
  it("measures the retracement of an up move from its end back to its start", () => {
    const l = fibLevels(p("2026-01-01", 100), p("2026-01-02", 200));
    expect(l[0]).toEqual({ ratio: 0, price: 200 });
    expect(l.find((x) => x.ratio === 0.5)?.price).toBe(150);
    expect(l.at(-1)).toEqual({ ratio: 1, price: 100 });
  });
});

describe("measureText", () => {
  it("shows the signed change, percent and bars", () => {
    expect(measureText(p("2026-01-01", 100), p("2026-01-02", 110), 5)).toBe("+10.00 (+10.00%) · 5 bars");
    expect(measureText(p("2026-01-01", 100), p("2026-01-02", 90), 1)).toBe("−10.00 (−10.00%) · 1 bar");
  });
});

describe("geometry", () => {
  it("measures the distance from a point to a segment, clamped at its ends", () => {
    const seg = [{ x: 0, y: 0 }, { x: 10, y: 0 }] as const;
    expect(distanceToSegment({ x: 5, y: 3 }, seg)).toBe(3);
    expect(distanceToSegment({ x: 13, y: 4 }, seg)).toBe(5);
  });

  const trend: Drawing = { id: "t", kind: "trend", a: p("2026-01-01", 100), b: p("2026-01-05", 100) };
  const rect: Drawing = { id: "r", kind: "rect", a: p("2026-01-02", 120), b: p("2026-01-04", 80) };

  it("extends a ray to the right edge along its slope", () => {
    const ray: Drawing = { id: "y", kind: "ray", a: p("2026-01-01", 100), b: p("2026-01-02", 110) };
    const [s] = segments(ray, at, 100);
    expect(s?.[1]).toEqual({ x: 100, y: 10 }); // from (10,100) falling 1 per x to the edge at x=100
  });

  it("hit-tests the topmost drawing near the click, and nothing far away", () => {
    expect(hitTest([trend], { x: 30, y: 103 }, at, 200)).toBe("t");
    expect(hitTest([trend], { x: 30, y: 160 }, at, 200)).toBeNull();
    expect(hitTest([trend, rect], { x: 20, y: 100 }, at, 200)).toBe("r"); // both pass through here; the later one sits on top
  });
});

describe("snapPrice", () => {
  it("snaps to the nearest of open, high, low, close", () => {
    expect(snapPrice(9.4, { open: 10, high: 12, low: 9, close: 11 })).toBe(9);
    expect(snapPrice(5, undefined)).toBe(5);
  });
});

describe("dragDrawing", () => {
  const times = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"];
  const trend: Drawing = { id: "t", kind: "trend", a: p("2026-01-02", 100), b: p("2026-01-04", 110) };

  it("moves one handle and leaves the other", () => {
    const r = dragDrawing(trend, "b", p("2026-01-04", 110), p("2026-01-05", 120), times);
    expect(r.a).toEqual(trend.a);
    expect(r.b).toEqual(p("2026-01-05", 120));
  });

  it("shifts the whole drawing by candles and price", () => {
    const r = dragDrawing(trend, "move", p("2026-01-03", 105), p("2026-01-04", 108), times);
    expect(r.a).toEqual(p("2026-01-03", 103));
    expect(r.b).toEqual(p("2026-01-05", 113));
  });

  it("stops at the ends of the chart instead of leaving it", () => {
    const r = dragDrawing(trend, "move", p("2026-01-03", 105), p("2026-01-05", 105), times); // +2 candles
    expect(r.a.time).toBe("2026-01-04");
    expect(r.b?.time).toBe("2026-01-05"); // clamped, not past the last candle
  });

  it("only moves a horizontal line in price", () => {
    const h: Drawing = { id: "h", kind: "hline", a: p("2026-01-03", 50) };
    expect(dragDrawing(h, "move", p("2026-01-02", 50), p("2026-01-05", 57), times).a).toEqual(p("2026-01-03", 57));
  });
});

describe("parseDrawings keeps a drawing's style", () => {
  const base = { id: "a", kind: "trend", a: { time: "2026-01-01", price: 1 }, b: { time: "2026-01-02", price: 2 } };
  it("keeps a valid colour and width", () => {
    expect(parseDrawings([{ ...base, color: "#e5484d", width: 3 }])[0]).toMatchObject({ color: "#e5484d", width: 3 });
  });
  it("drops a colour or width it does not recognise, but keeps the drawing", () => {
    const [d] = parseDrawings([{ ...base, color: "javascript:alert(1)", width: 99 }]);
    expect(d).toBeDefined();
    expect(d && "color" in d).toBe(false);
    expect(d && "width" in d).toBe(false);
  });
});

describe("describeDrawing", () => {
  it("names a horizontal line by its price", () => {
    expect(describeDrawing({ id: "h", kind: "hline", a: p("2026-01-03", 50) })).toBe("Horizontal line · 50.00");
  });
  it("describes a two-point drawing by its dates and prices", () => {
    expect(describeDrawing({ id: "t", kind: "trend", a: p("2026-07-28", 66.984), b: p("2026-09-07", 78.7) })).toBe(
      "Trend line · 07-28 to 09-07 · 66.98 to 78.70",
    );
  });
  it("shows clock times for minute-chart drawings", () => {
    const d: Drawing = { id: "m", kind: "measure", a: { time: 1_700_000_000, price: 1 }, b: { time: 1_700_003_600, price: 2 } };
    expect(describeDrawing(d)).toContain("22:13 to 23:13");
  });
});

describe("the new drawing kinds", () => {
  const trio = (kind: "long" | "short"): Drawing => ({ id: "p", kind, a: p("2026-01-03", 100), b: p("2026-01-03", 95), c: p("2026-01-03", 110) });

  it("says how many clicks each kind needs", () => {
    expect(["hline", "vline", "text"].map((k) => pointsNeeded(k as Drawing["kind"]))).toEqual([1, 1, 1]);
    expect(["trend", "ray", "rect", "fib", "measure"].map((k) => pointsNeeded(k as Drawing["kind"]))).toEqual([2, 2, 2, 2, 2]);
    expect(["channel", "long", "short"].map((k) => pointsNeeded(k as Drawing["kind"]))).toEqual([3, 3, 3]);
  });

  it("keeps a valid channel, position, vertical line and note, and drops incomplete or oversized ones", () => {
    const a = p("2026-01-01", 1);
    const out = parseDrawings([
      { id: "c", kind: "channel", a, b: a, c: a },
      { id: "c2", kind: "channel", a, b: a },
      { id: "l", kind: "long", a, b: a, c: a },
      { id: "s", kind: "short", a, b: a },
      { id: "v", kind: "vline", a },
      { id: "t", kind: "text", a, text: "  bought here  " },
      { id: "t2", kind: "text", a, text: "   " },
      { id: "t3", kind: "text", a, text: "x".repeat(121) },
      { id: "t4", kind: "text", a },
    ]);
    expect(out.map((d) => d.id)).toEqual(["c", "l", "v", "t"]);
    expect(out.find((d) => d.id === "t")?.text).toBe("bought here");
  });

  it("draws a vertical line from the top of the pane to the bottom", () => {
    const [s] = segments({ id: "v", kind: "vline", a: p("2026-01-03", 0) }, at, 500, { height: 300 });
    expect(s).toEqual([{ x: 30, y: 0 }, { x: 30, y: 300 }]);
  });

  it("draws a channel's parallel line at the same slope through the third point", () => {
    const base = { id: "c", kind: "channel" as const, a: p("2026-01-01", 100), b: p("2026-01-05", 100), c: p("2026-01-03", 90) };
    const segs = segments(base, at, 500);
    expect(segs).toHaveLength(2);
    const [line, parallel] = segs as [Segment, Segment];
    expect(parallel[0].y - line[0].y).toBe(10); // the third point sits 10 px below (price 90 against 100)
    expect(channelOffset({ x: 0, y: 0 }, { x: 10, y: 10 }, { x: 5, y: 8 })).toBe(3); // 3 px below the sloping base at x=5
    expect(segments({ ...base, c: undefined }, at, 500)).toHaveLength(1); // still being drawn
  });

  it("draws a position as an entry line and two boxes, each hit-testable", () => {
    const segs = segments(trio("long"), at, 500, { box: 100 });
    expect(segs.length).toBe(1 + 4 + 4);
    expect(hitTest([trio("long")], { x: 40, y: 100 }, at, 500, 7, { box: 100 })).toBe("p"); // on the entry line
    expect(hitTest([trio("long")], { x: 400, y: 100 }, at, 500, 7, { box: 100 })).toBeNull(); // beyond the box
    const tall: Drawing = { id: "t", kind: "long", a: p("2026-01-03", 100), b: p("2026-01-03", 80), c: p("2026-01-03", 140) }; // y: entry 100, stop 120, target 60
    expect(hitTest([tall], { x: 60, y: 80 }, at, 500, 7, { box: 100 })).toBe("t"); // inside the green zone, 20 px from every edge
    expect(hitTest([tall], { x: 60, y: 110 }, at, 500, 7, { box: 100 })).toBe("t"); // inside the red zone, 10 px from every edge
    expect(hitTest([tall], { x: 60, y: 20 }, at, 500, 7, { box: 100 })).toBeNull(); // above the target
    expect(hitTest([tall], { x: 300, y: 80 }, at, 500, 7, { box: 100 })).toBeNull(); // to the right of the box
  });

  it("makes a note hit-testable around its text", () => {
    const t: Drawing = { id: "t", kind: "text", a: p("2026-01-03", 50), text: "hello" };
    expect(hitTest([t], { x: 40, y: 140 }, at, 500)).toBe("t"); // a few pixels inside the box
    expect(hitTest([t], { x: 400, y: 140 }, at, 500)).toBeNull();
  });
});

describe("positionStats", () => {
  it("is risk, reward and their ratio, with the signed moves as a share of the entry", () => {
    const s = positionStats({ id: "p", kind: "long", a: p("2026-01-03", 100), b: p("2026-01-03", 95), c: p("2026-01-03", 110) });
    expect(s).toMatchObject({ risk: 5, reward: 10, ratio: 2, riskPct: 5, rewardPct: 10, targetMovePct: 10, stopMovePct: -5 });
  });
  it("gives no ratio when the stop sits on the entry, and nothing before all three points exist", () => {
    expect(positionStats({ id: "p", kind: "long", a: p("x", 100), b: p("x", 100), c: p("x", 110) })?.ratio).toBeNull();
    expect(positionStats({ id: "p", kind: "short", a: p("x", 100), b: p("x", 105) })).toBeNull();
  });
  it("describes a position with its ratio", () => {
    const d: Drawing = { id: "p", kind: "short", a: p("2026-01-03", 100), b: p("2026-01-03", 105), c: p("2026-01-03", 90) };
    expect(describeDrawing(d)).toBe("Short position · entry 100.00 · stop 105.00 · target 90.00 · 2.0:1");
  });
});

describe("dragging the new kinds", () => {
  const times = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"];
  const pos: Drawing = { id: "p", kind: "long", a: p("2026-01-03", 100), b: p("2026-01-03", 95), c: p("2026-01-03", 110) };

  it("moves a vertical line along time only", () => {
    const v: Drawing = { id: "v", kind: "vline", a: p("2026-01-02", 50) };
    expect(dragDrawing(v, "move", p("2026-01-02", 50), p("2026-01-04", 80), times).a).toEqual(p("2026-01-04", 50));
  });
  it("moves a position's stop or target in price only, under the entry's date", () => {
    expect(dragDrawing(pos, "b", p("2026-01-03", 95), p("2026-01-05", 92), times).b).toEqual(p("2026-01-03", 92));
    expect(dragDrawing(pos, "c", p("2026-01-03", 110), p("2026-01-01", 120), times).c).toEqual(p("2026-01-03", 120));
  });
  it("moving a position's entry carries the stop and target with it, keeping their prices", () => {
    const r = dragDrawing(pos, "a", p("2026-01-03", 100), p("2026-01-04", 101), times);
    expect(r.a).toEqual(p("2026-01-04", 101));
    expect(r.b).toEqual(p("2026-01-04", 95));
    expect(r.c).toEqual(p("2026-01-04", 110));
  });
  it("shifts the whole position by candles and price when its body is dragged", () => {
    const r = dragDrawing(pos, "move", p("2026-01-03", 100), p("2026-01-04", 103), times);
    expect([r.a.time, r.a.price, r.b?.price, r.c?.price]).toEqual(["2026-01-04", 103, 98, 113]);
  });
  it("drags a channel's third point freely, and moves all three points together", () => {
    const ch: Drawing = { id: "c", kind: "channel", a: p("2026-01-01", 100), b: p("2026-01-03", 110), c: p("2026-01-02", 90) };
    expect(dragDrawing(ch, "c", p("2026-01-02", 90), p("2026-01-04", 85), times).c).toEqual(p("2026-01-04", 85));
    const moved = dragDrawing(ch, "move", p("2026-01-02", 95), p("2026-01-03", 96), times);
    expect([moved.a.time, moved.b?.time, moved.c?.time]).toEqual(["2026-01-02", "2026-01-04", "2026-01-03"]);
  });
});
