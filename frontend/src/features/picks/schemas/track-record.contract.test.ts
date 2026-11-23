import { describe, expect, it } from "vitest";
import record from "@/shared/api/__fixtures__/track-record.json";
import { trackRecordSchema } from "./track-record";

describe("track-record schema vs. a real API response", () => {
  it("parses, and carries every bucket and the limits of the test", () => {
    const r = trackRecordSchema.safeParse(record);
    expect(r.success, JSON.stringify(r.error?.issues)).toBe(true);
    const t = r.data?.data;
    expect(Object.keys(t?.by_bucket["20"] ?? {})).toEqual(expect.arrayContaining(["buy_zone", "wait_pullback", "watch", "avoid"]));
    expect(t?.notes.length).toBeGreaterThan(0); // the numbers are never shown without their caveats
  });
});
