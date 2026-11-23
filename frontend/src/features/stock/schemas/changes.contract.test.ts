import { describe, expect, it } from "vitest";
import changes from "@/shared/api/__fixtures__/changes.json";
import { changesSchema } from "./changes";

describe("changes schema vs. a real API response", () => {
  it("parses, with at most five dated, toned sentences", () => {
    const r = changesSchema.safeParse(changes);
    expect(r.success, JSON.stringify(r.error?.issues)).toBe(true);
    const d = r.data?.data;
    expect(d?.enough_history).toBe(true);
    expect(d?.changes.length).toBeLessThanOrEqual(5);
    expect(d?.changes.every((c) => c.text.length > 10)).toBe(true);
    expect(d?.previous_bar_date && d.bar_date && d.previous_bar_date < d.bar_date).toBeTruthy();
  });
});
