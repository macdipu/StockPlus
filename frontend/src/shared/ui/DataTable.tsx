"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState, type ReactNode } from "react";
import { sortRows, type Cell } from "./sort-rows";

export interface Column<R> {
  key: string;
  label: string;
  /** Right-align numbers. */
  align?: "left" | "right";
  /** The sortable value; defaults to `row[key]`. */
  value?: (row: R) => Cell;
  render?: (row: R) => ReactNode;
  sortable?: boolean;
  /** Drop this column on phone widths (secondary detail); the rest stay. */
  hideNarrow?: boolean;
}

interface Props<R> {
  rows: readonly R[];
  columns: ReadonlyArray<Column<R>>;
  rowKey: (row: R) => string;
  caption: string;
  defaultSort?: { key: string; desc: boolean };
  /** Make rows navigable: clicking a row (or pressing Enter on it) goes here. */
  rowHref?: (row: R) => string | null;
  empty?: string;
  maxHeight?: string;
}

export function DataTable<R>({ rows, columns, rowKey, caption, defaultSort, rowHref, empty = "No matches", maxHeight }: Props<R>) {
  const router = useRouter();
  const [sort, setSort] = useState(defaultSort ?? null);

  const sorted = useMemo(() => {
    const col = sort && columns.find((c) => c.key === sort.key);
    if (!col || !sort) return rows;
    return sortRows(rows, col.value ?? ((r) => (r as Record<string, Cell>)[col.key]), sort.desc);
  }, [rows, columns, sort]);

  const toggle = (key: string) => setSort((s) => ({ key, desc: s?.key === key ? !s.desc : true }));

  return (
    <div className="tablewrap" style={maxHeight ? { maxHeight } : undefined}>
      <table>
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {columns.map((c) => {
              const active = sort?.key === c.key;
              const sortable = c.sortable !== false;
              return (
                <th
                  key={c.key}
                  scope="col"
                  className={`${sortable ? "sortable" : ""} ${c.align === "right" ? "r" : ""} ${c.hideNarrow ? "hide-sm" : ""}`}
                  aria-sort={active ? (sort.desc ? "descending" : "ascending") : sortable ? "none" : undefined}
                >
                  {sortable ? (
                    <button type="button" onClick={() => toggle(c.key)} style={{ all: "unset", cursor: "pointer" }}>
                      {c.label}
                      {active ? (sort.desc ? " ▾" : " ▴") : ""}
                    </button>
                  ) : (
                    c.label
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="mute">{empty}</td>
            </tr>
          ) : (
            sorted.map((row) => {
              const href = rowHref?.(row) ?? null;
              return (
                <tr
                  key={rowKey(row)}
                  className={href ? "clickable" : undefined}
                  onClick={href ? () => router.push(href) : undefined}
                  onKeyDown={href ? (e) => e.key === "Enter" && router.push(href) : undefined}
                  tabIndex={href ? 0 : undefined}
                >
                  {columns.map((c) => (
                    <td key={c.key} className={`${c.align === "right" ? "r num" : ""} ${c.hideNarrow ? "hide-sm" : ""}`.trim() || undefined}>
                      {c.render ? c.render(row) : String((row as Record<string, unknown>)[c.key] ?? "–")}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
