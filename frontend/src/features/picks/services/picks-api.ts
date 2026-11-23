import { request } from "@/shared/api";
import { trackRecordSchema } from "../schemas/track-record";
import { picksResponseSchema, type PickFilters } from "../schemas/picks";

export const picksApi = {
  picks: (f: PickFilters, limit = 300) =>
    request("/market/picks", {
      query: {
        sectors: f.include,
        exclude_sectors: f.exclude,
        categories: f.category || null,
        min_value_mn: f.minValueMn || null,
        buckets: f.buckets,
        limit,
      },
      schema: picksResponseSchema,
    }),
  trackRecord: () => request("/market/picks/track-record", { schema: trackRecordSchema }),
};
