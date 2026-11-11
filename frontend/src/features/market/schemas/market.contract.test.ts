import { describe, expect, it } from "vitest";
import { z } from "zod";
import { envelope, quoteSchema } from "@/shared/api";
import movers from "@/shared/api/__fixtures__/movers.json";
import pe from "@/shared/api/__fixtures__/pe.json";
import range52 from "@/shared/api/__fixtures__/range52.json";
import sectors from "@/shared/api/__fixtures__/sectors.json";
import { peSummarySchema, rangeRowSchema, sectorRowSchema } from "./market";

describe("market schemas vs. real API responses", () => {
  it.each([
    ["sectors", envelope(z.array(sectorRowSchema)), sectors],
    ["movers", envelope(z.array(quoteSchema)), movers],
    ["pe", envelope(peSummarySchema), pe],
    ["52-week", envelope(z.array(rangeRowSchema)), range52],
  ])("%s", (_name, schema, fixture) => {
    const r = schema.safeParse(fixture);
    expect(r.success, JSON.stringify(r.error?.issues)).toBe(true);
  });
});
