import type { ReactNode } from "react";

/** A labelled value, laid out in a `.kv` grid. */
export function Stat({ label, children, tone }: { label: string; children: ReactNode; tone?: "up" | "dn" | "" }) {
  return (
    <div>
      <span>{label}</span>
      <b className={tone || undefined}>{children}</b>
    </div>
  );
}

export function KeyValueTable({ rows }: { rows: ReadonlyArray<readonly [string, ReactNode]> }) {
  return (
    <table>
      <tbody>
        {rows.map(([k, v]) => (
          <tr key={k}>
            <th scope="row">{k}</th>
            <td>{v}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
