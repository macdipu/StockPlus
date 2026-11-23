import type { Quote } from "@/shared/api";

/** Rank symbols for a typed query: exact code, code prefix, code contains, a company-name word that starts with
 * it, name contains, then sector contains. Ties go to the busier share. `names` maps code → company name. */
export function matchSymbols(quotes: readonly Quote[], query: string, names: ReadonlyMap<string, string>, limit = 8): Quote[] {
  const q = query.trim().toUpperCase();
  if (!q) return [];
  const scored: Array<[number, Quote]> = [];
  for (const quote of quotes) {
    const code = quote.symbol.toUpperCase();
    const name = (names.get(quote.symbol) ?? "").toUpperCase();
    const score =
      code === q ? 0
      : code.startsWith(q) ? 1
      : code.includes(q) ? 2
      : name.split(/[^A-Z0-9]+/).some((w) => w.startsWith(q)) ? 3
      : name.includes(q) ? 4
      : (quote.sector ?? "").toUpperCase().includes(q) ? 5
      : -1;
    if (score >= 0) scored.push([score, quote]);
  }
  return scored.sort((a, b) => a[0] - b[0] || b[1].volume - a[1].volume).slice(0, limit).map(([, quote]) => quote);
}
