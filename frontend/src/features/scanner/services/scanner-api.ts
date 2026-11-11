import { z } from "zod";
import { envelope, nothing, request } from "@/shared/api";
import { fieldsSchema, presetSchema, savedScanSchema, scanResultSchema } from "../schemas/scanner";
import type { ScanBody } from "../utils/rules";

export interface PresetFilters {
  category: string;
  minValueMn: string;
  live: string;
}

export const scannerApi = {
  presets: () => request("/scanner/presets", { schema: envelope(z.array(presetSchema)) }),
  fields: () => request("/scanner/fields", { schema: envelope(fieldsSchema) }),
  runPreset: (key: string, f: PresetFilters, limit = 200) =>
    request(`/scanner/presets/${encodeURIComponent(key)}`, {
      query: { limit, categories: f.category || null, min_value_mn: f.minValueMn || null, live: f.live || null },
      schema: scanResultSchema,
    }),
  runCustom: (body: ScanBody) => request("/scanner/run", { method: "POST", body, schema: scanResultSchema }),
  savedScans: () => request("/saved-scans", { auth: true, schema: envelope(z.array(savedScanSchema)) }),
  saveScan: (name: string, definition: ScanBody) =>
    request("/saved-scans", { method: "POST", auth: true, body: { name, definition }, schema: envelope(savedScanSchema) }),
  deleteScan: (id: string) => request(`/saved-scans/${id}`, { method: "DELETE", auth: true, schema: nothing }),
};
