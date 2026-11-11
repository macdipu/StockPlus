import { describe, expect, it } from "vitest";
import { toCsv } from "./csv";

describe("toCsv", () => {
  it("writes a header and one line per row, in column order", () => {
    expect(toCsv([{ b: 2, a: "x" }, { a: "y", b: null }], ["a", "b"])).toBe("a,b\nx,2\ny,\n");
  });

  it("quotes cells with commas, quotes and newlines", () => {
    expect(toCsv([{ a: 'He said "hi", ok', b: "line1\nline2" }], ["a", "b"])).toBe('a,b\n"He said ""hi"", ok","line1\nline2"\n');
  });

  it("joins list cells with spaces", () => {
    expect(toCsv([{ patterns: ["Doji", "Hammer"] }], ["patterns"])).toBe("patterns\nDoji Hammer\n");
  });

  it("neutralises spreadsheet formulas in text but not negative numbers", () => {
    const csv = toCsv([{ n: '=HYPERLINK("http://evil")', m: "+1", k: "-cmd", z: "@SUM(A1)", neg: -5 }], ["n", "m", "k", "z", "neg"]);
    expect(csv).toBe(`n,m,k,z,neg\n"'=HYPERLINK(""http://evil"")",'+1,'-cmd,'@SUM(A1),-5\n`);
  });

  it("handles no rows", () => {
    expect(toCsv([], ["a"])).toBe("a\n");
  });
});
