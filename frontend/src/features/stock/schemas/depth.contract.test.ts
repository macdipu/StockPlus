import { describe, expect, it } from "vitest";
import depth from "@/shared/api/__fixtures__/depth.json";
import { depthSchema } from "./depth";

describe("depth schema vs. a real API response", () => {
  it("parses, with buyers high-to-low and sellers low-to-high", () => {
    const r = depthSchema.safeParse(depth);
    expect(r.success, JSON.stringify(r.error?.issues)).toBe(true);
    const d = r.data?.data;
    const buy = d?.buyers.levels.map((l) => l.price) ?? [];
    const sell = d?.sellers.levels.map((l) => l.price) ?? [];
    expect(buy).toEqual([...buy].sort((a, b) => b - a));
    expect(sell).toEqual([...sell].sort((a, b) => a - b));
    expect(d?.buyers.total_quantity).toBe(d?.buyers.levels.reduce((n, l) => n + l.quantity, 0));
  });
});
