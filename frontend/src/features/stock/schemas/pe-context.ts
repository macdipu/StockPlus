import { z } from "zod";
import { envelope } from "@/shared/api";

const n = z.number().nullable();

/** Only what the stock page compares a share's P/E with: the market median and each sector's median. */
export const peContextSchema = envelope(
  z.object({
    market: z.object({ median_pe: n, weighted_pe: n }),
    by_sector: z.record(z.string(), z.object({ instruments: z.number(), median_pe: n })),
  }),
);
