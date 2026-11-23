import { z } from "zod";
import { envelope } from "@/shared/api";

/** The index's daily closes (the chart endpoint also carries more than this page needs). */
export const indexChartSchema = envelope(z.object({ candles: z.object({ time: z.array(z.number()), close: z.array(z.number()) }) }));
