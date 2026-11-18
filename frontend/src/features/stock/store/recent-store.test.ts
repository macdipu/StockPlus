import { beforeEach, describe, expect, it } from "vitest";
import { clearRecent, getRecent, pushRecent } from "./recent-store";

describe("recent symbols", () => {
  beforeEach(() => clearRecent());

  it("keeps the newest first without duplicates", () => {
    pushRecent("gp");
    pushRecent("BRACBANK");
    pushRecent("GP");
    expect(getRecent()).toEqual(["GP", "BRACBANK"]);
  });

  it("is capped at eight", () => {
    for (let i = 0; i < 12; i++) pushRecent(`S${i}`);
    expect(getRecent()).toHaveLength(8);
    expect(getRecent()[0]).toBe("S11");
  });

  it("clears", () => {
    pushRecent("GP");
    clearRecent();
    expect(getRecent()).toEqual([]);
  });
});
