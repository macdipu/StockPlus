/** Number formatting shared by every table and card. Missing values render as an en dash. */

export const DASH = "–";

export function num(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return DASH;
  return v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** Signed percentage, e.g. +1.2%. */
export function pct(v: number | null | undefined, digits = 1): string {
  if (v == null || Number.isNaN(v)) return DASH;
  return `${v >= 0 ? "+" : "−"}${num(Math.abs(v), digits)}%`;
}

/** Plain (unsigned) percentage, e.g. 45%. */
export function pctPlain(v: number | null | undefined, digits = 0): string {
  return v == null || Number.isNaN(v) ? DASH : `${num(v, digits)}%`;
}

export type Tone = "up" | "dn" | "";

export function tone(v: number | null | undefined): Tone {
  if (v == null || Number.isNaN(v) || v === 0) return "";
  return v > 0 ? "up" : "dn";
}

/** Whole-number grouping for volumes, counts, market caps. */
export function int(v: number | null | undefined): string {
  return num(v, 0);
}

/** BDT crore (1 crore = 10 million), the unit Bangladeshi market caps are quoted in. */
export function crore(v: number | null | undefined): string {
  return v == null || Number.isNaN(v) ? DASH : `${num(v / 1e7, 0)} cr`;
}

export function text(v: unknown): string {
  if (v == null || v === "") return DASH;
  return Array.isArray(v) ? v.join(", ") || DASH : String(v);
}
