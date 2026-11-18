import { describe, expect, it } from "vitest";
import { SECTIONS, routes, sectionFor, viewFor } from "./navigation";

describe("navigation", () => {
  it("maps paths to sections and views", () => {
    expect(sectionFor("/")?.key).toBe("market");
    expect(sectionFor("/stock/GP")?.key).toBe("stock");
    const find = sectionFor("/find/rules/golden_cross")!;
    expect(find.key).toBe("find");
    expect(viewFor(find, "/find")?.key).toBe("picks");
    expect(viewFor(find, "/find/rules/golden_cross")?.key).toBe("rules");
    expect(viewFor(find, "/find/table")?.key).toBe("table");
  });

  it("builds links", () => {
    expect(routes.findRules("rsi oversold")).toBe("/find/rules/rsi%20oversold");
    expect(routes.findTable("Food & Allied")).toBe("/find/table?sector=Food%20%26%20Allied");
  });

  it("every view has a plan and a description", () => {
    for (const v of SECTIONS.flatMap((s) => s.views)) {
      expect(v.description.length).toBeGreaterThan(10);
      expect(["free", "pro"]).toContain(v.plan);
    }
  });
});
