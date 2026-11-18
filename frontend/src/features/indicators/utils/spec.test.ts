import { describe, expect, it } from "vitest";
import type { CatalogEntry } from "../schemas/catalog";
import { clampValues, formatSpec, parseSpec, searchCatalog, specLabel, specValues } from "./spec";

const entry = (id: string, name: string, params: CatalogEntry["params"] = [], description = "x".repeat(30)): CatalogEntry => ({
  id, name, group: "Momentum", placement: "pane", description, params, outputs: [{ key: id, label: name, kind: "line" }], scale: null, levels: [], repaints: false, requires: [],
});
const p = (key: string, def: number, min = 1, max = 500, integer = true) => ({ key, label: key, default: def, min, max, integer });
const macd = entry("macd", "MACD", [p("fast", 12), p("slow", 26), p("signal", 9)]);
const rsi = entry("rsi", "Relative Strength Index", [p("length", 14, 2)]);
const obv = entry("obv", "On Balance Volume");

describe("indicator specs", () => {
  it("formats and parses the API grammar", () => {
    expect(formatSpec(macd)).toBe("macd(12,26,9)");
    expect(formatSpec(rsi, { length: 21 })).toBe("rsi(21)");
    expect(formatSpec(obv)).toBe("obv");
    expect(parseSpec("macd(12, 26, 9)")).toEqual({ id: "macd", args: [12, 26, 9] });
    expect(parseSpec("OBV")).toEqual({ id: "obv", args: [] });
    expect(parseSpec("rsi(abc)")).toBeNull();
    expect(parseSpec("not a spec")).toBeNull();
  });

  it("reads values back with defaults for what a spec leaves out", () => {
    expect(specValues(macd, "macd(10)")).toEqual({ fast: 10, slow: 26, signal: 9 });
    expect(specLabel(macd, "macd(12,26,9)")).toBe("MACD (12, 26, 9)");
    expect(specLabel(obv, "obv")).toBe("On Balance Volume");
  });

  it("clamps to the catalog's ranges and makes integers whole", () => {
    expect(clampValues(rsi, { length: 1 })).toEqual({ length: 2 });
    expect(clampValues(rsi, { length: 14.6 })).toEqual({ length: 15 });
    expect(clampValues(rsi, { length: Number.NaN })).toEqual({ length: 14 });
  });

  it("searches by name, id and description, best matches first", () => {
    const all = [rsi, macd, obv, entry("cmf", "Chaikin Money Flow", [], "Shows buying pressure from volume")];
    expect(searchCatalog(all, "rsi").map((e) => e.id)).toEqual(["rsi"]);
    expect(searchCatalog(all, "money")[0]?.id).toBe("cmf");
    expect(searchCatalog(all, "pressure").map((e) => e.id)).toEqual(["cmf"]);
    expect(searchCatalog(all, "").length).toBe(4);
    expect(searchCatalog(all, "zzz")).toEqual([]);
  });
});
