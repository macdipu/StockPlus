import { describe, expect, it } from "vitest";
import { z } from "zod";
import { envelope } from "@/shared/api";
import bars from "@/shared/api/__fixtures__/bars.json";
import company from "@/shared/api/__fixtures__/company.json";
import { barSchema, companySchema } from "./company";

describe("company schemas vs. real API responses", () => {
  it.each([
    ["company", envelope(companySchema), company],
    ["bars", envelope(z.array(barSchema)), bars],
  ])("%s", (_name, schema, fixture) => {
    const r = schema.safeParse(fixture);
    expect(r.success, JSON.stringify(r.error?.issues)).toBe(true);
  });
});
