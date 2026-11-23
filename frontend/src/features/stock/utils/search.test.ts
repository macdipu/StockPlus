import { describe, expect, it } from "vitest";
import type { Quote } from "@/shared/api";
import { matchSymbols } from "./search";

const q = (symbol: string, volume: number, sector = "Misc"): Quote => ({
  symbol, ltp: 10, ycp: 10, open: 10, high: 10, low: 10, close: 10, change: 0, percent: 0, volume,
  value_mn: 1, trades: 1, category: "A", board: null, sector, asset_type: "EQ", trade_time: null,
});
const quotes = [q("GP", 5, "Telecom"), q("GPHISPAT", 9), q("BXPHARMA", 1, "Pharma"), q("SQURPHARMA", 7, "Pharma")];
const names = new Map([
  ["GP", "Grameenphone Ltd."],
  ["GPHISPAT", "GPH Ispat Limited"],
  ["BXPHARMA", "Beximco Pharmaceuticals PLC."],
  ["SQURPHARMA", "Square Pharmaceuticals PLC."],
]);
const codes = (query: string) => matchSymbols(quotes, query, names).map((r) => r.symbol);

describe("matchSymbols", () => {
  it("puts an exact code first, then prefixes by volume", () => expect(codes("gp")).toEqual(["GP", "GPHISPAT"]));
  it("finds a share by company name", () => expect(codes("grameen")).toEqual(["GP"]));
  it("matches a word inside the name", () => expect(codes("ispat")).toEqual(["GPHISPAT"]));
  it("ranks name matches above sector matches", () => expect(codes("pharma")).toEqual(["SQURPHARMA", "BXPHARMA"]));
  it("returns nothing for an empty query", () => expect(codes("  ")).toEqual([]));
});
