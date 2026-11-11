import { describe, expect, it } from "vitest";
import { crore, DASH, int, num, pct, pctPlain, text, tone } from "./format";

describe("format", () => {
  it("renders missing values as a dash, never NaN or undefined", () => {
    for (const f of [num, pct, pctPlain, int, crore]) {
      expect(f(null)).toBe(DASH);
      expect(f(undefined)).toBe(DASH);
      expect(f(Number.NaN)).toBe(DASH);
    }
    expect(text(null)).toBe(DASH);
    expect(text("")).toBe(DASH);
    expect(text([])).toBe(DASH);
  });

  it("groups thousands and fixes decimals", () => {
    expect(num(1234567.891)).toBe("1,234,567.89");
    expect(num(3, 0)).toBe("3");
    expect(num(0.5, 3)).toBe("0.500");
    expect(int(1234.6)).toBe("1,235");
  });

  it("signs percentages with a real minus and keeps zero positive", () => {
    expect(pct(1.234)).toBe("+1.2%");
    expect(pct(-1.234)).toBe("−1.2%");
    expect(pct(0)).toBe("+0.0%");
    expect(pct(-0.04, 1)).toBe("−0.0%");
    expect(pctPlain(45.2)).toBe("45%");
  });

  it("classifies tone and converts to crore", () => {
    expect(tone(1)).toBe("up");
    expect(tone(-1)).toBe("dn");
    expect(tone(0)).toBe("");
    expect(tone(null)).toBe("");
    expect(crore(102_384_000_000)).toBe("10,238 cr");
  });

  it("joins lists", () => {
    expect(text(["Doji", "Hammer"])).toBe("Doji, Hammer");
    expect(text(0)).toBe("0");
  });
});
