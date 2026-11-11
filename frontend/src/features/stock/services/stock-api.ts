import { z } from "zod";
import { envelope, metaSchema, request } from "@/shared/api";
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
