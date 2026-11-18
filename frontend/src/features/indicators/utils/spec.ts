import type { CatalogEntry } from "../schemas/catalog";

/**
 * An indicator request as text: "rsi(14)", "macd(12,26,9)", "obv". Positional parameters follow the order the
 * catalog lists them; the server fills in anything omitted. This is the same grammar the API accepts.
 */

const fmt = (v: number) => (Number.isInteger(v) ? String(v) : String(Number(v.toPrecision(6))));

export function formatSpec(entry: Pick<CatalogEntry, "id" | "params">, values?: Readonly<Record<string, number>>): string {
  if (entry.params.length === 0) return entry.id;
  return `${entry.id}(${entry.params.map((p) => fmt(values?.[p.key] ?? p.default)).join(",")})`;
}

export interface ParsedSpec {
  id: string;
  args: number[];
}

export function parseSpec(spec: string): ParsedSpec | null {
  const m = /^([a-z0-9_]+)(?:\(([^)]*)\))?$/i.exec(spec.trim());
  if (!m?.[1]) return null;
  const args = (m[2] ?? "").split(",").map((a) => a.trim()).filter(Boolean).map(Number);
  return args.some((a) => !Number.isFinite(a)) ? null : { id: m[1].toLowerCase(), args };
}

/** The parameter values a spec string stands for, with defaults for anything it leaves out. */
export function specValues(entry: CatalogEntry, spec: string): Record<string, number> {
  const parsed = parseSpec(spec);
  return Object.fromEntries(entry.params.map((p, i) => [p.key, parsed?.args[i] ?? p.default]));
}

/** "RSI (14)", "MACD (12, 26, 9)", "On Balance Volume": what a person reads on a chip. */
export function specLabel(entry: CatalogEntry, spec: string): string {
  if (entry.params.length === 0) return entry.name;
  const v = specValues(entry, spec);
  return `${entry.name} (${entry.params.map((p) => fmt(v[p.key] ?? p.default)).join(", ")})`;
}

/** Clamp each value to its range and make integers whole, as the server does. */
export function clampValues(entry: CatalogEntry, values: Readonly<Record<string, number>>): Record<string, number> {
  return Object.fromEntries(
    entry.params.map((p) => {
      const raw = values[p.key] ?? p.default;
      const v = Math.min(Math.max(Number.isFinite(raw) ? raw : p.default, p.min), p.max);
      return [p.key, p.integer ? Math.round(v) : v];
    }),
  );
}

/** Indicators matching a search text, by name, id or description, best matches first. */
export function searchCatalog(entries: readonly CatalogEntry[], query: string): CatalogEntry[] {
  const q = query.trim().toLowerCase();
  if (!q) return [...entries];
  const scored: Array<[number, CatalogEntry]> = [];
  for (const e of entries) {
    const name = e.name.toLowerCase();
    const score = e.id === q ? 0 : name.startsWith(q) ? 1 : name.split(/\s+/).some((w) => w.startsWith(q)) ? 2 : name.includes(q) || e.id.includes(q) ? 3 : e.description.toLowerCase().includes(q) ? 4 : -1;
    if (score >= 0) scored.push([score, e]);
  }
  return scored.sort((a, b) => a[0] - b[0] || a[1].name.localeCompare(b[1].name)).map(([, e]) => e);
}
