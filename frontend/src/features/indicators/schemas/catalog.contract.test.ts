import { describe, expect, it } from "vitest";
import { envelope } from "@/shared/api";
import catalog from "@/shared/api/__fixtures__/indicators.json";
import { catalogSchema } from "./catalog";

describe("indicator catalog schema vs. a real API response", () => {
  it("parses and lists at least 80 indicators with a description each", () => {
    const r = envelope(catalogSchema).safeParse(catalog);
    expect(r.success, JSON.stringify(r.error?.issues)).toBe(true);
    expect(r.data?.data.indicators.length).toBeGreaterThanOrEqual(80);
    expect(r.data?.data.indicators.every((i) => i.description.length >= 25)).toBe(true);
  });
});
