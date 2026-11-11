import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";
import { buildUrl, envelope, request, setRefreshHandler } from "./client";
import { ApiError } from "./errors";
import { tokenStore } from "./token";

const ok = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" }, ...init });
const problem = (status: number, extra: object = {}) =>
  new Response(JSON.stringify({ title: "Nope", status, detail: "because", requestId: "r1", ...extra }), {
    status,
    headers: { "content-type": "application/problem+json", "x-request-id": "hdr-id" },
  });

const schema = envelope(z.object({ n: z.number() }));
let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  tokenStore.set(null);
  setRefreshHandler(null);
});
afterEach(() => vi.unstubAllGlobals());

describe("buildUrl", () => {
  it("joins arrays, skips empty values and encodes", () => {
    expect(buildUrl("/x", { a: 1, b: ["GP", "BATBC"], c: null, d: undefined, e: "", f: "a b&c", g: false })).toBe(
      "/api/v1/x?a=1&b=GP%2CBATBC&f=a+b%26c&g=false",
    );
    expect(buildUrl("/x")).toBe("/api/v1/x");
    expect(buildUrl("/x", {})).toBe("/api/v1/x");
  });
});

describe("request", () => {
  it("returns parsed data and sends JSON bodies", async () => {
    fetchMock.mockResolvedValueOnce(ok({ data: { n: 1 }, meta: {} }));
    const r = await request("/p", { method: "POST", body: { a: 1 }, schema });
    expect(r.data.n).toBe(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/p");
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"a":1}');
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("turns problem+json into an ApiError carrying its extras", async () => {
    fetchMock.mockResolvedValueOnce(problem(400, { unknown: ["NOPE"] }));
    const e = await request("/p", { schema }).catch((x: unknown) => x);
    expect(e).toBeInstanceOf(ApiError);
    const err = e as ApiError;
    expect([err.status, err.title, err.detail, err.requestId]).toEqual([400, "Nope", "because", "hdr-id"]);
    expect(err.extra).toEqual({ unknown: ["NOPE"] });
  });

  it("survives a non-JSON error body (a proxy error page)", async () => {
    fetchMock.mockResolvedValueOnce(new Response("<html>Bad gateway</html>", { status: 502, statusText: "Bad Gateway" }));
    const err = (await request("/p", { schema }).catch((x: unknown) => x)) as ApiError;
    expect([err.status, err.title, err.detail]).toEqual([502, "Bad Gateway", null]);
  });

  it("reports a network failure as status 0, not a TypeError", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("failed to fetch"));
    const err = (await request("/p", { schema }).catch((x: unknown) => x)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
  });

  it("flags a response that does not match the schema instead of rendering junk", async () => {
    fetchMock.mockResolvedValueOnce(ok({ data: { n: "not a number" }, meta: {} }));
    const err = (await request("/p", { schema }).catch((x: unknown) => x)) as ApiError;
    expect(err.status).toBe(502);
    expect(err.title).toBe("Unexpected response");
    expect(err.detail).toContain("/p");
    expect(err.detail).toContain("data.n");
  });

  it("accepts a 204 with the nothing-schema", async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    await expect(request("/p", { method: "DELETE", schema: z.undefined() })).resolves.toBeUndefined();
  });

  it("only sends the access token to endpoints that ask for auth", async () => {
    tokenStore.set("tok");
    fetchMock.mockImplementation(() => Promise.resolve(ok({ data: { n: 1 }, meta: {} }))); // a fresh body per call
    await request("/public", { schema });
    await request("/private", { schema, auth: true });
    const auth = (i: number) => ((fetchMock.mock.calls[i] as [string, RequestInit])[1].headers as Record<string, string>).Authorization;
    expect(auth(0)).toBeUndefined();
    expect(auth(1)).toBe("Bearer tok");
  });
});

describe("authenticated retry", () => {
  it("refreshes once on 401, then retries with the new token", async () => {
    tokenStore.set("old");
    setRefreshHandler(async () => {
      tokenStore.set("new");
      return true;
    });
    fetchMock.mockResolvedValueOnce(problem(401)).mockResolvedValueOnce(ok({ data: { n: 2 }, meta: {} }));
    const r = await request("/me", { schema, auth: true });
    expect(r.data.n).toBe(2);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(((fetchMock.mock.calls[1] as [string, RequestInit])[1].headers as Record<string, string>).Authorization).toBe("Bearer new");
  });

  it("gives up when the refresh fails, and does not loop", async () => {
    setRefreshHandler(async () => false);
    fetchMock.mockImplementation(() => Promise.resolve(problem(401)));
    const err = (await request("/me", { schema, auth: true }).catch((x: unknown) => x)) as ApiError;
    expect(err.isUnauthorized).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("retries only once even if the retried call is 401 again", async () => {
    setRefreshHandler(async () => true);
    fetchMock.mockImplementation(() => Promise.resolve(problem(401)));
    await expect(request("/me", { schema, auth: true })).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("shares ONE refresh between concurrent 401s (the refresh token rotates)", async () => {
    let refreshes = 0;
    setRefreshHandler(async () => {
      refreshes += 1;
      await new Promise((r) => setTimeout(r, 10));
      return true;
    });
    let calls = 0;
    fetchMock.mockImplementation(() => Promise.resolve(++calls <= 3 ? problem(401) : ok({ data: { n: 1 }, meta: {} })));
    const results = await Promise.all([1, 2, 3].map(() => request("/me", { schema, auth: true })));
    expect(results).toHaveLength(3);
    expect(refreshes).toBe(1);
  });

  it("never refreshes for public endpoints", async () => {
    const handler = vi.fn(async () => true);
    setRefreshHandler(handler);
    fetchMock.mockImplementation(() => Promise.resolve(problem(401)));
    await expect(request("/public", { schema })).rejects.toBeInstanceOf(ApiError);
    expect(handler).not.toHaveBeenCalled();
  });
});
