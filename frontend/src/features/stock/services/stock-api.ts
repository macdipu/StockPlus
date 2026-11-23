import { z } from "zod";
import { envelope, metaSchema, request } from "@/shared/api";
import { candlesSchema } from "../schemas/candles";
import {
  analysisSchema,
  intradayBarSchema,
  technicalBarSchema,
  vpaLegendSchema,
  vpaRowSchema,
} from "../schemas/analysis";

const sym = (s: string) => encodeURIComponent(s.toUpperCase());

export const stockApi = {
  analysis: (symbol: string) => request(`/stocks/${sym(symbol)}/analysis`, { schema: envelope(analysisSchema) }),
  technicals: (symbol: string, limit = 260) =>
    request(`/stocks/${sym(symbol)}/technicals`, { query: { limit }, schema: envelope(z.array(technicalBarSchema)) }),
  candles: (symbol: string, limit = 2000) => request(`/stocks/${sym(symbol)}/candles`, { query: { limit }, schema: candlesSchema }),
  vpa: (symbol: string, days = 20) =>
    request(`/stocks/${sym(symbol)}/vpa`, {
      query: { days },
      schema: z.object({ data: z.array(vpaRowSchema), meta: metaSchema.extend({ legend: vpaLegendSchema }) }),
    }),
  intraday: (symbol: string) =>
    request(`/stocks/${sym(symbol)}/intraday`, {
      schema: z.object({ data: z.array(intradayBarSchema), meta: metaSchema.extend({ note: z.string().nullish() }) }),
    }),
};
