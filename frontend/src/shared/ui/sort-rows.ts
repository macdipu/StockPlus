export type Cell = string | number | boolean | null | undefined | readonly unknown[];

/** Missing values always sort last, whichever direction is chosen. */
export function compareCells(a: Cell, b: Cell): number {
  if (a == null) return 1;
  if (b == null) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
}

export function sortRows<R>(rows: readonly R[], value: (r: R) => Cell, desc: boolean): R[] {
  return rows
    .map((row, i) => ({ row, i, v: value(row) }))
    .sort((x, y) => {
      if (x.v == null || y.v == null) return compareCells(x.v, y.v) || x.i - y.i; // nulls last in both directions
      const c = compareCells(x.v, y.v);
      return (desc ? -c : c) || x.i - y.i; // stable
    })
    .map((x) => x.row);
}
