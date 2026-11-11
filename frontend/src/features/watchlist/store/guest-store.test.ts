import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_GUEST_SYMBOLS, GUEST_KEY, clearGuestSymbols, getGuestSymbols, guestListWasCustomised, parseSymbols, setGuestSymbols, subscribeGuest,
} from "./guest-store";

beforeEach(() => {
  window.localStorage.clear();
  clearGuestSymbols();
});
afterEach(() => vi.restoreAllMocks());

describe("guest watchlist", () => {
  it("defaults until the visitor changes it", () => {
    expect(getGuestSymbols()).toEqual(DEFAULT_GUEST_SYMBOLS);
    expect(guestListWasCustomised()).toBe(false);
  });

  it("persists, normalises and notifies", () => {
    const l = vi.fn();
    const off = subscribeGuest(l);
    setGuestSymbols(["gp", "BATBC"]);
    expect(getGuestSymbols()).toEqual(["GP", "BATBC"]); // normalised when written, not just when read
    expect(window.localStorage.getItem(GUEST_KEY)).toBe('["GP","BATBC"]');
    expect(guestListWasCustomised()).toBe(true);
    expect(l).toHaveBeenCalled();
    off();
  });

  it("returns a stable reference while nothing changed (useSyncExternalStore requires it)", () => {
    setGuestSymbols(["GP"]);
    expect(getGuestSymbols()).toBe(getGuestSymbols());
  });

  it("parses defensively: bad JSON, wrong types and duplicates", () => {
    expect(parseSymbols(null)).toEqual(DEFAULT_GUEST_SYMBOLS);
    expect(parseSymbols("{oops")).toEqual(DEFAULT_GUEST_SYMBOLS);
    expect(parseSymbols('{"a":1}')).toEqual(DEFAULT_GUEST_SYMBOLS);
    expect(parseSymbols("[1,2]")).toEqual(DEFAULT_GUEST_SYMBOLS);
    expect(parseSymbols('[" gp ","GP","","robi"]')).toEqual(["GP", "ROBI"]);
  });

  it("keeps working when storage is unavailable (private mode)", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("denied", "SecurityError");
    });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("denied", "SecurityError");
    });
    expect(() => setGuestSymbols(["GP"])).not.toThrow();
    expect(() => getGuestSymbols()).not.toThrow();
  });
});
