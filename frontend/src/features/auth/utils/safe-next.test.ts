import { describe, expect, it } from "vitest";
import { safeNext } from "./safe-next";

describe("safeNext", () => {
  it("keeps same-site paths", () => {
    expect(safeNext("/scanner/hammer")).toBe("/scanner/hammer");
    expect(safeNext("/data?sector=Bank")).toBe("/data?sector=Bank");
  });

  it("refuses anything that could leave the site", () => {
    for (const bad of ["https://evil.example", "//evil.example", "/\\evil.example", "javascript:alert(1)", "evil", "", null, undefined, "/ok\r\nSet-Cookie: x=1"]) {
      expect(safeNext(bad as string | null | undefined)).toBe("/");
    }
    expect(safeNext("//evil.example", "/home")).toBe("/home");
  });
});
