"use client";

import { num } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { Empty, ErrorNotice, Loading } from "@/shared/ui/Notice";
import { useVpa } from "../hooks/use-stock-queries";

const bias = (label: string, legend: Record<string, { bias: string }>) => legend[label]?.bias;

export function VpaCard({ symbol }: { symbol: string }) {
  const q = useVpa(symbol);
  return (
    <Card title="Volume-price analysis (daily)">
      {q.isPending ? <Loading onRetry={() => void q.refetch()} /> : q.isError ? <ErrorNotice error={q.error} onRetry={() => void q.refetch()} /> : (() => {
        const { data: rows, meta } = q.data;
        const signals = rows.filter((r) => r.vpa).reverse();
        if (!signals.length) return <Empty>No VPA signals in the last 20 sessions.</Empty>;
        return (
          <>
            <table className="small">
              <tbody>
                {signals.map((r) => (
                  <tr key={r.date}>
                    <td style={{ whiteSpace: "nowrap" }}>{r.date}</td>
                    <td className={bias(r.vpa ?? "", meta.legend) === "bullish" ? "up" : bias(r.vpa ?? "", meta.legend) === "bearish" ? "dn" : ""}>{r.vpa}</td>
                    <td className="mute">vol {num(r.vol_rel)}× · spread {num(r.spread_rel)}× · close at {Math.round((r.close_pos ?? 0) * 100)}% of range</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <details className="small">
              <summary className="mute">What these labels mean</summary>
              <ul className="plain">
                {Object.entries(meta.legend).map(([k, v]) => <li key={k}><b>{k}</b>: {v.meaning}</li>)}
              </ul>
            </details>
          </>
        );
      })()}
    </Card>
  );
}
