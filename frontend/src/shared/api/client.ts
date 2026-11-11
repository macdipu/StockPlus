import { z } from "zod";
import { env } from "@/shared/lib/env";
import { ApiError, problemFrom } from "./errors";
import { tokenStore } from "./token";

export const metaSchema = z.looseObject({ requestId: z.string().nullish(), disclaimer: z.string().optional() });

/** Every JSON endpoint wraps its payload as `{ data, meta }`. */
export function envelope<T extends z.ZodType>(data: T) {
  return z.object({ data, meta: metaSchema });
}

export type Query = Record<string, string | number | boolean | readonly string[] | null | undefined>;

export interface RequestOptions<T extends z.ZodType> {
  schema: T;
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  query?: Query;
  body?: unknown;
  /** Send the access token and refresh it once on a 401. Default: false (public endpoints). */
  auth?: boolean;
  signal?: AbortSignal;
}

type RefreshHandler = () => Promise<boolean>;
let refreshHandler: RefreshHandler | null = null;
let inFlightRefresh: Promise<boolean> | null = null;

/** The auth feature registers how to obtain a new access token; shared/ stays free of feature imports. */
export function setRefreshHandler(fn: RefreshHandler | null): void {
  refreshHandler = fn;
}

/** Concurrent 401s share ONE refresh: the refresh token rotates, so two parallel calls would race. */
export async function refreshSession(): Promise<boolean> {
  if (!refreshHandler) return false;
  inFlightRefresh ??= refreshHandler().finally(() => {
    inFlightRefresh = null;
  });
  return inFlightRefresh;
}

export function buildUrl(path: string, query?: Query): string {
  const url = `${env.NEXT_PUBLIC_API_BASE}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v == null || v === "") continue;
    params.set(k, Array.isArray(v) ? v.join(",") : String(v));
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

async function send(path: string, o: Omit<RequestOptions<z.ZodType>, "schema">): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (o.body !== undefined) headers["Content-Type"] = "application/json";
  const token = o.auth ? tokenStore.get() : null;
  if (token) headers.Authorization = `Bearer ${token}`;
  try {
    return await fetch(buildUrl(path, o.query), {
      method: o.method ?? "GET",
      headers,
      body: o.body === undefined ? undefined : JSON.stringify(o.body),
      credentials: "same-origin",
      signal: o.signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(0, "Network error", "Could not reach the server. Check your connection.", null);
  }
}

export async function request<T extends z.ZodType>(path: string, o: RequestOptions<T>): Promise<z.infer<T>> {
  let res = await send(path, o);
  if (res.status === 401 && o.auth && (await refreshSession())) res = await send(path, o); // retry once
  if (!res.ok) throw await problemFrom(res);
  if (res.status === 204) return o.schema.parse(undefined);
  const json: unknown = await res.json();
  const parsed = o.schema.safeParse(json);
  if (!parsed.success) {
    // The API and this client disagree about a response shape: surface it loudly instead of rendering junk.
    throw new ApiError(
      502,
      "Unexpected response",
      `${path}: ${parsed.error.issues[0]?.path.join(".") || "(root)"} — ${parsed.error.issues[0]?.message}`,
      res.headers.get("x-request-id"),
    );
  }
  return parsed.data;
}

export const nothing = z.undefined();
