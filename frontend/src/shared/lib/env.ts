import { z } from "zod";

const schema = z.object({
  /** Base path of the API. Same-origin by default: Next proxies `/api/*` to the FastAPI replicas. */
  NEXT_PUBLIC_API_BASE: z
    .string()
    .regex(/^\/[A-Za-z0-9/_-]*$/, "must be an absolute path such as /api/v1")
    .default("/api/v1"),
});

// Referenced literally so Next can inline NEXT_PUBLIC_* values into the client bundle.
export const env = schema.parse({ NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || undefined });
