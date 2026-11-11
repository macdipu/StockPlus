import { z } from "zod";
import { envelope, request } from "@/shared/api";
import { watchlistSchema } from "../schemas/watchlist";

const one = envelope(watchlistSchema);

export const watchlistApi = {
  list: () => request("/watchlists", { auth: true, schema: envelope(z.array(watchlistSchema)) }),
  create: (name: string, symbols: readonly string[]) =>
    request("/watchlists", { method: "POST", auth: true, body: { name, symbols }, schema: one }),
  add: (id: string, symbols: readonly string[]) =>
    request(`/watchlists/${id}/symbols`, { method: "POST", auth: true, body: { symbols }, schema: one }),
  remove: (id: string, symbol: string) =>
    request(`/watchlists/${id}/symbols/${encodeURIComponent(symbol)}`, { method: "DELETE", auth: true, schema: one }),
};
