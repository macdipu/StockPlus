import { z } from "zod";

export const catalogEntrySchema = z.object({
  id: z.string(),
  name: z.string(),
  group: z.string(),
  placement: z.enum(["overlay", "pane"]),
  description: z.string(),
  params: z.array(z.object({ key: z.string(), label: z.string(), default: z.number(), min: z.number(), max: z.number(), integer: z.boolean() })),
  outputs: z.array(z.object({ key: z.string(), label: z.string(), kind: z.enum(["line", "histogram", "area", "dots"]) })),
  scale: z.tuple([z.number(), z.number()]).nullable(),
  levels: z.array(z.number()),
  repaints: z.boolean(),
  /** Price columns beyond the close that it reads: open, high, low, volume. Empty = closes only. */
  requires: z.array(z.string()),
});
export type CatalogEntry = z.infer<typeof catalogEntrySchema>;

export const catalogSchema = z.object({ version: z.string(), groups: z.array(z.string()), indicators: z.array(catalogEntrySchema) });
export type Catalog = z.infer<typeof catalogSchema>;
