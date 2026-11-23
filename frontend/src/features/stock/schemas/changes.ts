import { z } from "zod";
import { envelope } from "@/shared/api";

export const changesSchema = envelope(
  z.object({
    symbol: z.string(),
    bar_date: z.string().nullable(),
    previous_bar_date: z.string().nullable(),
    enough_history: z.boolean(),
    changes: z.array(z.object({ kind: z.string(), text: z.string(), tone: z.enum(["good", "bad", "info"]) })),
  }),
);
export type Changes = z.infer<typeof changesSchema>["data"];
