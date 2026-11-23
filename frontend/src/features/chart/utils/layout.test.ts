import { describe, expect, it } from "vitest";
import { BASE_HEIGHT, PANE_HEIGHT, chartHeight, paneHeight } from "./layout";

describe("chartHeight", () => {
  it("adds a full panel for each open indicator panel", () => {
    expect(chartHeight(0, 0)).toBe(BASE_HEIGHT);
    expect(chartHeight(2, 0)).toBe(BASE_HEIGHT + 2 * PANE_HEIGHT);
  });
  it("gives collapsed panels only a thin strip", () => {
    expect(chartHeight(2, 1)).toBeLessThan(chartHeight(2, 0));
    expect(chartHeight(2, 2)).toBeLessThan(chartHeight(2, 1));
    expect(chartHeight(2, 2)).toBeGreaterThan(BASE_HEIGHT);
  });
  it("ignores a collapsed count that cannot be right", () => {
    expect(chartHeight(1, 5)).toBe(chartHeight(1, 1));
    expect(chartHeight(1, -3)).toBe(chartHeight(1, 0));
  });
  it("tells the library a smaller drawing area for a collapsed panel", () => {
    expect(paneHeight(true)).toBeLessThan(paneHeight(false));
  });
});
