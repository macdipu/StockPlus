import { envelope, request } from "@/shared/api";
import { chartSchema, type Resolution } from "../schemas/chart";

export const chartApi = {
  chart: (symbol: string, resolution: Resolution, indicators: readonly string[], pages = 1, signal?: AbortSignal) =>
    request(`/charts/${encodeURIComponent(symbol.toUpperCase())}`, {
      query: { resolution, indicators: indicators.join(","), pages },
      schema: envelope(chartSchema),
      signal,
    }),
};
