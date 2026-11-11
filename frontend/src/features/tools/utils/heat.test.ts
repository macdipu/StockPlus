import { describe, expect, it } from "vitest";
import { heatColor, parseSymbols } from "./heat";

describe("heatColor", () => {
  it("is white at zero, blue for positive and red for negative", () => {
    expect(heatColor(0)).toBe("rgb(255, 255, 255)");
    const blue = heatColor(1).match(/\d+/g)!.map(Number);
    const red = heatColor(-1).match(/\d+/g)!.map(Number);
    expect(blue[2]).toBeGreaterThan(blue[0]!);
    expect(red[0]).toBeGreaterThan(red[2]!);
  });

  it("clamps and tolerates missing values", () => {
    expect(heatColor(5)).toBe(heatColor(1));
    expect(heatColor(-5)).toBe(heatColor(-1));
    expect(heatColor(null)).toBe("transparent");
    expect(heatColor(Number.NaN)).toBe("transparent");
  });
});

describe("parseSymbols", () => {
  it("splits on commas and spaces, upper-cases and dedupes", () => {
    expect(parseSymbols(" gp, batbc  robi,GP,, ")).toEqual(["GP", "BATBC", "ROBI"]);
    expect(parseSymbols("")).toEqual([]);
  });
});
