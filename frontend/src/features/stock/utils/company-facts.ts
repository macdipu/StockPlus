import type { Company } from "@/features/company";

/** Small readers over the company payload, shared by the summary and the valuation views. */

export const ratio = (c: Company | undefined, key: string): number | null => c?.ratios.find((r) => r.key === key)?.value ?? null;

/** "Paid a cash dividend in 4 of the last 5 years", as numbers. */
export function dividendRecord(c: Company | undefined): { paid: number; of: number } | null {
  for (const f of c?.flags ?? []) {
    const m = /paid a cash dividend in (\d+) of the last (\d+) years/i.exec(f.text);
    if (m) return { paid: Number(m[1]), of: Number(m[2]) };
  }
  return null;
}

export const FINANCIAL = /bank|financial|insurance|leasing|nbfi/i;
