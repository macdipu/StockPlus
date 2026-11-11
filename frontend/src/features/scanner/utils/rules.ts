import type { ApiRule } from "../schemas/scanner";

/** What the user edits: every input is a string, exactly as typed. */
export interface DraftRule {
  field: string;
  op: string;
  value: string;
  field2: string;
}

export interface DraftFilters {
  category: string; // "" = all
  minValueMn: string; // "" = no minimum
  live: "" | "true" | "false"; // "" = default for the scan
}

export const NO_OPERAND_OPS = new Set(["is_true", "is_false"]);
export const LIST_OPS = new Set(["between", "in", "not_in"]);
export const CROSS_OPS = new Set(["crosses_above", "crosses_below"]);

export const newRule = (): DraftRule => ({ field: "close", op: ">", value: "", field2: "sma50" });
export const defaultRules = (): DraftRule[] => [{ field: "rsi14", op: "between", value: "50,70", field2: "" }];

const scalar = (s: string): string | number => {
  const t = s.trim();
  return t !== "" && Number.isFinite(Number(t)) ? Number(t) : t;
};

/** "50, 70" → [50, 70]; "A,B" → ["A","B"]. Empty entries are dropped. */
export const parseList = (s: string): Array<string | number> =>
  s.split(",").map((p) => p.trim()).filter(Boolean).map(scalar);

export function toApiRule(r: DraftRule): ApiRule {
  const out: ApiRule = { field: r.field, op: r.op };
  if (NO_OPERAND_OPS.has(r.op)) return out;
  if (r.field2) {
    out.field2 = r.field2;
    return out;
  }
  if (LIST_OPS.has(r.op)) out.value = parseList(r.value);
  else if (r.value.trim() !== "") out.value = scalar(r.value);
  return out;
}

/** The first problem with a draft rule, or null. Catches mistakes before a round trip. */
export function ruleProblem(r: DraftRule): string | null {
  if (!r.field) return "Choose a field.";
  if (NO_OPERAND_OPS.has(r.op) || r.field2) return null;
  if (r.op === "between") {
    const parts = parseList(r.value);
    return parts.length === 2 && parts.every((p) => typeof p === "number") ? null : `"${r.field}" between needs two numbers, e.g. 50,70.`;
  }
  if (LIST_OPS.has(r.op)) return parseList(r.value).length ? null : `"${r.field}" ${r.op} needs a comma-separated list.`;
  return r.value.trim() === "" ? `"${r.field}" ${r.op} needs a value or another field.` : null;
}

export interface ScanBody {
  rules: ApiRule[];
  match: "all" | "any";
  universe: { asset_types: string[]; categories?: string[]; min_value_mn?: number };
  limit: number;
  live?: boolean;
}

export function buildScanBody(rules: readonly DraftRule[], match: "all" | "any", f: DraftFilters, limit = 200): ScanBody {
  const min = Number(f.minValueMn);
  return {
    rules: rules.map(toApiRule),
    match,
    universe: {
      asset_types: ["EQ"],
      ...(f.category ? { categories: [f.category] } : {}),
      ...(f.minValueMn.trim() !== "" && Number.isFinite(min) && min > 0 ? { min_value_mn: min } : {}),
    },
    limit,
    ...(f.live ? { live: f.live === "true" } : {}),
  };
}

const display = (v: unknown): string => (Array.isArray(v) ? v.join(",") : v == null ? "" : String(v));

/** A saved definition → the editor's drafts (the inverse of `buildScanBody`). Unknown shapes degrade to empty. */
export function draftFromDefinition(def: Record<string, unknown>): { rules: DraftRule[]; match: "all" | "any"; filters: DraftFilters } {
  const rawRules = Array.isArray(def.rules) ? def.rules : [];
  const rules = rawRules.flatMap((r): DraftRule[] => {
    if (!r || typeof r !== "object") return [];
    const o = r as Record<string, unknown>;
    return typeof o.field === "string" && typeof o.op === "string"
      ? [{ field: o.field, op: o.op, value: display(o.value), field2: typeof o.field2 === "string" ? o.field2 : "" }]
      : [];
  });
  const u = (def.universe && typeof def.universe === "object" ? def.universe : {}) as Record<string, unknown>;
  const cats = Array.isArray(u.categories) ? u.categories : [];
  return {
    rules: rules.length ? rules : defaultRules(),
    match: def.match === "any" ? "any" : "all",
    filters: {
      category: typeof cats[0] === "string" ? cats[0] : "",
      minValueMn: typeof u.min_value_mn === "number" ? String(u.min_value_mn) : "",
      live: def.live === true ? "true" : def.live === false ? "false" : "",
    },
  };
}
