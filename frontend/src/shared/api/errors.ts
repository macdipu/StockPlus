/** An RFC 7807 problem+json response, or a transport failure, as one throwable type. */
export class ApiError extends Error {
  readonly status: number;
  readonly title: string;
  readonly detail: string | null;
  readonly requestId: string | null;
  /** Extra members the API attached to the problem (e.g. `unknown` symbols, `retry_after_s`). */
  readonly extra: Record<string, unknown>;

  constructor(status: number, title: string, detail: string | null, requestId: string | null, extra = {}) {
    super(detail ?? title);
    this.name = "ApiError";
    this.status = status;
    this.title = title;
    this.detail = detail;
    this.requestId = requestId;
    this.extra = extra;
  }

  get isUnauthorized(): boolean {
    return this.status === 401;
  }
}

const KNOWN = new Set(["type", "title", "status", "detail", "instance", "requestId"]);

export async function problemFrom(res: Response): Promise<ApiError> {
  const requestId = res.headers.get("x-request-id");
  try {
    const body: unknown = await res.json();
    if (body && typeof body === "object") {
      const b = body as Record<string, unknown>;
      const extra = Object.fromEntries(Object.entries(b).filter(([k]) => !KNOWN.has(k)));
      return new ApiError(
        res.status,
        typeof b.title === "string" ? b.title : res.statusText || "Request failed",
        typeof b.detail === "string" ? b.detail : null,
        requestId ?? (typeof b.requestId === "string" ? b.requestId : null),
        extra,
      );
    }
  } catch {
    // not JSON (a proxy error page, say): fall through
  }
  return new ApiError(res.status, res.statusText || "Request failed", null, requestId);
}

export function describeError(e: unknown): string {
  if (e instanceof ApiError) return e.detail ?? e.title;
  if (e instanceof Error) return e.message;
  return "Something went wrong";
}
