import { z } from "zod";
import { envelope, request } from "@/shared/api";

export const universeStatusSchema = envelope(
  z.object({
    ready: z.boolean(),
    version: z.number().nullable(),
    rows: z.number(),
    built_at_ms: z.number().nullable(),
    build_ms: z.number().nullable(),
    trade_time: z.string().nullable(),
  }),
);

const rescanSchema = envelope(z.object({ accepted: z.boolean(), version: z.number().nullable() }));

export const universeApi = {
  status: () => request("/scanner/universe", { schema: universeStatusSchema }),
  rescan: () => request("/scanner/rescan", { method: "POST", schema: rescanSchema }),
};
