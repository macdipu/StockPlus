import { describe, expect, it } from "vitest";
import {
  buildScanBody,
  defaultRules,
  draftFromDefinition,
  parseList,
  ruleProblem,
  toApiRule,
  type DraftFilters,
  type DraftRule,
} from "./rules";

const rule = (p: Partial<DraftRule>): DraftRule => ({ field: "rsi14", op: "<", value: "", field2: "", ...p });
const none: DraftFilters = { category: "", minValueMn: "", live: "" };

describe("toApiRule", () => {
  it("parses scalars as numbers when they are numbers", () => {
    expect(toApiRule(rule({ value: "30" }))).toEqual({ field: "rsi14", op: "<", value: 30 });
    expect(toApiRule(rule({ op: "==", field: "category", value: "A" }))).toEqual({ field: "category", op: "==", value: "A" });
    expect(toApiRule(rule({ value: " 1.5 " })).value).toBe(1.5);
    expect(toApiRule(rule({ value: "-2e3" })).value).toBe(-2000);
  });

  it("splits list operators", () => {
    expect(toApiRule(rule({ op: "between", value: "50, 70" }))).toEqual({ field: "rsi14", op: "between", value: [50, 70] });
    expect(toApiRule(rule({ op: "in", field: "category", value: "A,B," })).value).toEqual(["A", "B"]);
    expect(parseList(" , ")).toEqual([]);
  });

  it("prefers a second field over a value, and ignores operands for is_true", () => {
    expect(toApiRule(rule({ op: ">", value: "5", field2: "ema21" }))).toEqual({ field: "rsi14", op: ">", field2: "ema21" });
    expect(toApiRule(rule({ op: "is_true", field: "nr7", value: "junk", field2: "x" }))).toEqual({ field: "nr7", op: "is_true" });
  });

  it("does not turn blank or non-numeric text into 0", () => {
    expect(toApiRule(rule({ value: "" })).value).toBeUndefined();
    expect(toApiRule(rule({ value: "abc" })).value).toBe("abc");
  });
});

describe("ruleProblem", () => {
  it("accepts complete rules", () => {
    expect(ruleProblem(rule({ value: "30" }))).toBeNull();
    expect(ruleProblem(rule({ op: ">", field2: "sma50" }))).toBeNull();
    expect(ruleProblem(rule({ op: "is_false", field: "nr7" }))).toBeNull();
    expect(ruleProblem(rule({ op: "between", value: "1,2" }))).toBeNull();
    expect(ruleProblem(rule({ op: "in", field: "sector", value: "Bank" }))).toBeNull();
  });

  it("explains what is missing", () => {
    expect(ruleProblem(rule({ field: "" }))).toMatch(/field/i);
    expect(ruleProblem(rule({ value: "" }))).toMatch(/needs a value/);
    expect(ruleProblem(rule({ op: "between", value: "5" }))).toMatch(/two numbers/);
    expect(ruleProblem(rule({ op: "between", value: "a,b" }))).toMatch(/two numbers/);
    expect(ruleProblem(rule({ op: "in", value: " " }))).toMatch(/list/);
  });
});

describe("buildScanBody", () => {
  it("always restricts to equities and only adds filters that are set", () => {
    const b = buildScanBody([rule({ value: "30" })], "all", none);
    expect(b).toEqual({ rules: [{ field: "rsi14", op: "<", value: 30 }], match: "all", universe: { asset_types: ["EQ"] }, limit: 200 });
    const f = buildScanBody([rule({ value: "30" })], "any", { category: "A", minValueMn: "2.5", live: "false" });
    expect(f.universe).toEqual({ asset_types: ["EQ"], categories: ["A"], min_value_mn: 2.5 });
    expect(f.match).toBe("any");
    expect(f.live).toBe(false);
  });

  it("ignores junk turnover values", () => {
    expect(buildScanBody([], "all", { ...none, minValueMn: "abc" }).universe).toEqual({ asset_types: ["EQ"] });
    expect(buildScanBody([], "all", { ...none, minValueMn: "-1" }).universe).toEqual({ asset_types: ["EQ"] });
  });
});

describe("draftFromDefinition", () => {
  it("round-trips what buildScanBody produced", () => {
    const rules = [rule({ op: "between", value: "40,80" }), rule({ field: "close", op: ">", field2: "ema21" })];
    const filters: DraftFilters = { category: "B", minValueMn: "1", live: "true" };
    const back = draftFromDefinition(buildScanBody(rules, "any", filters) as unknown as Record<string, unknown>);
    expect(back.rules).toEqual(rules);
    expect(back.match).toBe("any");
    expect(back.filters).toEqual(filters);
  });

  it("degrades gracefully on malformed definitions", () => {
    for (const bad of [{}, { rules: "x" }, { rules: [null, 1, { field: 1 }] }, { rules: [], universe: 5 }]) {
      const d = draftFromDefinition(bad as Record<string, unknown>);
      expect(d.rules).toEqual(defaultRules());
      expect(d.match).toBe("all");
      expect(d.filters).toEqual(none);
    }
  });
});
