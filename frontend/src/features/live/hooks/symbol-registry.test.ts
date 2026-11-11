import { describe, expect, it, vi } from "vitest";
import { MAX_STREAM_SYMBOLS, SymbolRegistry } from "./symbol-registry";

describe("SymbolRegistry", () => {
  it("unions registrations, upper-cases, and reference-counts duplicates", () => {
    const r = new SymbolRegistry();
    const a = r.register(["gp", "BATBC"], false);
    const b = r.register(["GP"], false);
    expect(r.symbols()).toEqual(["BATBC", "GP"]);
    a();
    expect(r.symbols()).toEqual(["GP"]); // still wanted by b
    b();
    expect(r.symbols()).toEqual([]);
  });

  it("an unregister function is idempotent", () => {
    const r = new SymbolRegistry();
    const a = r.register(["GP"], false);
    r.register(["GP"], false);
    a();
    a();
    expect(r.symbols()).toEqual(["GP"]);
  });

  it("puts the page being viewed first and caps the stream at the API limit", () => {
    const r = new SymbolRegistry();
    r.register(Array.from({ length: 80 }, (_, i) => `W${String(i).padStart(3, "0")}`), false);
    r.register(["ZZZ"], true);
    const s = r.symbols();
    expect(s).toHaveLength(MAX_STREAM_SYMBOLS);
    expect(s[0]).toBe("ZZZ"); // a long watchlist can never crowd out the current page
  });

  it("does not list a symbol twice when it is both primary and watched", () => {
    const r = new SymbolRegistry();
    r.register(["GP", "ROBI"], false);
    r.register(["GP"], true);
    expect(r.symbols()).toEqual(["GP", "ROBI"]);
  });

  it("notifies listeners on every change", () => {
    const r = new SymbolRegistry();
    const l = vi.fn();
    const off = r.onChange(l);
    const unreg = r.register(["GP"], false);
    unreg();
    expect(l).toHaveBeenCalledTimes(2);
    off();
    r.register(["X"], false);
    expect(l).toHaveBeenCalledTimes(2);
  });
});
