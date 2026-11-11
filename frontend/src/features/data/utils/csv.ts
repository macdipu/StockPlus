/** CSV for the Data tab's export. Spreadsheets run text that starts with = + - @ as a formula, so text cells that
 *  do are prefixed with a quote (numbers, including negative ones, are left alone). */

function cell(v: unknown): string {
  if (v == null) return "";
  let s = Array.isArray(v) ? v.join(" ") : String(v);
  if (typeof v === "string" && /^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function toCsv(rows: ReadonlyArray<Record<string, unknown>>, columns: readonly string[]): string {
  return [columns.join(","), ...rows.map((r) => columns.map((c) => cell(r[c])).join(","))].join("\n") + "\n";
}

export function downloadCsv(filename: string, csv: string): void {
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
