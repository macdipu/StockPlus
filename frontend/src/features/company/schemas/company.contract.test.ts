import { describe, expect, it } from "vitest";
import { envelope } from "@/shared/api";
import company from "@/shared/api/__fixtures__/company.json";
import { companySchema } from "./company";

describe("company schema vs. a real API response", () => {
  it("company", () => {
    const r = envelope(companySchema).safeParse(company);
    expect(r.success, JSON.stringify(r.error?.issues)).toBe(true);
  });
});
