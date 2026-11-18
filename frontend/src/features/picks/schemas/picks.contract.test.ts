import { describe, expect, it } from "vitest";
import picks from "@/shared/api/__fixtures__/picks.json";
import { picksResponseSchema } from "./picks";

describe("picks schema vs. a real API response", () => {
  it("parses, and banks and insurance were left out", () => {
    const r = picksResponseSchema.safeParse(picks);
    expect(r.success, JSON.stringify(r.error?.issues)).toBe(true);
    expect(r.data?.data.some((p) => p.sector === "Bank" || p.sector === "Insurance")).toBe(false);
  });
});
