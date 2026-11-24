import { describe, expect, it } from "vitest";
import { startsNavigation, type ClickInfo } from "./nav-progress";

const here = { pathname: "/find", origin: "http://localhost:3000" };
const click = (over: Partial<ClickInfo> = {}): ClickInfo => ({ href: "/stock/GP", target: null, download: false, defaultPrevented: false, button: 0, modifier: false, ...over });

describe("startsNavigation", () => {
  it("is true for an ordinary link to another page of the site", () => {
    expect(startsNavigation(click(), here)).toBe(true);
    expect(startsNavigation(click({ href: "http://localhost:3000/market" }), here)).toBe(true);
  });
  it("is false when the browser or the page handles the click another way", () => {
    expect(startsNavigation(click({ modifier: true }), here)).toBe(false);
    expect(startsNavigation(click({ button: 1 }), here)).toBe(false);
    expect(startsNavigation(click({ target: "_blank" }), here)).toBe(false);
    expect(startsNavigation(click({ defaultPrevented: true }), here)).toBe(false);
    expect(startsNavigation(click({ download: true }), here)).toBe(false);
  });
  it("is false for the same page, another site, API links and nothing", () => {
    expect(startsNavigation(click({ href: "/find#top" }), here)).toBe(false);
    expect(startsNavigation(click({ href: "/find?x=1" }), here)).toBe(false);
    expect(startsNavigation(click({ href: "https://example.com/x" }), here)).toBe(false);
    expect(startsNavigation(click({ href: "/api/v1/stocks/GP/analysis" }), here)).toBe(false);
    expect(startsNavigation(click({ href: null }), here)).toBe(false);
  });
});
