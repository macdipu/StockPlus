import { z } from "zod";
import { envelope, request } from "@/shared/api";

const rows = envelope(z.array(z.record(z.string(), z.unknown())));

export type DataTab = "matrix" | "ta";

export const dataApi = {
  matrix: (sector: string | null) => request("/market/data-matrix", { query: { sector }, schema: rows }),
  ta: (sector: string | null) => request("/market/ta-values", { query: { sector }, schema: rows }),
};
