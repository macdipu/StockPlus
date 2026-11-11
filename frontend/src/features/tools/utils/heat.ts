/** Correlation → background colour: red (−1) through white (0) to blue (+1). Always light enough for dark text. */
export function heatColor(v: number | null): string {
  if (v == null || Number.isNaN(v)) return "transparent";
  const x = Math.max(-1, Math.min(1, v));
  const t = Math.abs(x);
  const [r, g, b] = x >= 0 ? [37, 99, 235] : [220, 38, 38];
  const mix = (c: number) => Math.round(255 + (c - 255) * t * 0.75);
  return `rgb(${mix(r)}, ${mix(g)}, ${mix(b)})`;
}

export const parseSymbols = (raw: string): string[] => [...new Set(raw.split(/[\s,]+/).map((s) => s.trim().toUpperCase()).filter(Boolean))];
