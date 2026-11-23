import { describe, expect, it } from "vitest";
import { distanceToSegment, fibLevels, hitTest, measureText, parseDrawings, segments, snapPrice, type Drawing, type DrawPoint } from "./drawings";

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
