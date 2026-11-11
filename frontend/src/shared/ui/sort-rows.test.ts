import { describe, expect, it } from "vitest";
import { sortRows } from "./sort-rows";

const rows = [
  { s: "B", v: 2 },
  { s: "A", v: null },
  { s: "C", v: 10 },
  { s: "D", v: 2 },
];
const order = (r: typeof rows) => r.map((x) => x.s).join("");

describe("sortRows", () => {
  it("sorts numbers both ways and always puts missing values last", () => {
    expect(order(sortRows(rows, (r) => r.v, false))).toBe("BDCA");
    expect(order(sortRows(rows, (r) => r.v, true))).toBe("CBDA");
  });

  it("is stable: ties keep their input order", () => {
    expect(order(sortRows(rows, (r) => r.v, true))).toBe("CBDA"); // B before D, as given
    expect(order(sortRows(rows, (r) => r.v, false))).toBe("BDCA");
  });

  it("sorts text naturally and case-insensitively", () => {
    const t = [{ s: "x10" }, { s: "X2" }, { s: "a" }];
    expect(sortRows(t, (r) => r.s, false).map((r) => r.s)).toEqual(["a", "X2", "x10"]);
  });

  it("does not mutate its input", () => {
    const copy = [...rows];
    sortRows(rows, (r) => r.v, true);
    expect(rows).toEqual(copy);
  });
});
