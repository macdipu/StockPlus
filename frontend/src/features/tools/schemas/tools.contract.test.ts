import { describe, expect, it } from "vitest";
import { envelope } from "@/shared/api";
import correlation from "@/shared/api/__fixtures__/correlation.json";
import ret from "@/shared/api/__fixtures__/return.json";
import { correlationSchema, returnSchema } from "./tools";

describe("tools schemas vs. real API responses", () => {
  it("return and correlation", () => {
    expect(envelope(returnSchema).safeParse(ret).success).toBe(true);
    const c = envelope(correlationSchema).safeParse(correlation);
    expect(c.success).toBe(true);
    if (c.success) expect(c.data.data.matrix).toHaveLength(c.data.data.symbols.length);
  });
});
