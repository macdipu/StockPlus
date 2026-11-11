import { z } from "zod";
import { eventMetaSchema, feedStatusSchema, marketSchema, quoteSchema } from "@/shared/api";

/** The SSE contract (ADR 0006), parsed defensively: a malformed event is dropped, never thrown into React. */

export const snapshotEvent = z.object({
  market: marketSchema.nullable(),
  quotes: z.record(z.string(), quoteSchema),
  feed: feedStatusSchema,
});

export const quoteEvent = quoteSchema.extend({ _meta: eventMetaSchema });

export const marketEvent = marketSchema.extend({ _meta: eventMetaSchema });

export const heartbeatEvent = z.object({ feed: feedStatusSchema });

export const universeEvent = z.object({ version: z.number(), rows: z.number() });

export function parseEvent<T extends z.ZodType>(schema: T, data: string): z.infer<T> | null {
  try {
    const r = schema.safeParse(JSON.parse(data));
    return r.success ? r.data : null;
  } catch {
    return null;
  }
}
