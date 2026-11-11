import { z } from "zod";

export const watchlistSchema = z.object({
  id: z.string(),
  name: z.string(),
  symbols: z.array(z.string()),
  created_at: z.string(),
  updated_at: z.string(),
});
export type Watchlist = z.infer<typeof watchlistSchema>;
