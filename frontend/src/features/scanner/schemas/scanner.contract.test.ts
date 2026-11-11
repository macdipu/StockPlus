import { describe, expect, it } from "vitest";
import { z } from "zod";
import { envelope } from "@/shared/api";
import fields from "@/shared/api/__fixtures__/fields.json";
import presets from "@/shared/api/__fixtures__/presets.json";
import scan from "@/shared/api/__fixtures__/scan-preset.json";
import { fieldsSchema, presetSchema, scanResultSchema } from "./scanner";

describe("scanner schemas vs. real API responses", () => {
  it("presets, fields and a scan result", () => {
    expect(envelope(z.array(presetSchema)).safeParse(presets).success).toBe(true);
    expect(envelope(fieldsSchema).safeParse(fields).success).toBe(true);
    const r = scanResultSchema.safeParse(scan);
    expect(r.success, JSON.stringify(r.error?.issues)).toBe(true);
    if (r.success) expect(r.data.meta.matched).toBeLessThanOrEqual(r.data.meta.scanned);
  });

  it("knows every operator the rule builder offers", () => {
    expect(fields.data.ops).toEqual(expect.arrayContaining(["between", "crosses_above", "is_true", "contains"]));
  });
});
