"use client";

import { Card } from "@/shared/ui/Card";
import { Empty, ErrorNotice, Loading } from "@/shared/ui/Notice";
import { useIntraday } from "../hooks/use-stock-queries";
import { IntradayChart } from "./IntradayChart";

const MIN_MINUTES = 8; // fewer minute bars than this is a dot or two, not a chart

/** `day` = the exchange date these minute bars belong to (the session date). */
export function IntradayCard({ symbol, day }: { symbol: string; day: string }) {
  const q = useIntraday(symbol);
  return (
    <Card title="Intraday (1-minute, recorded live)">
      {q.isPending ? <Loading onRetry={() => void q.refetch()} /> : q.isError ? <ErrorNotice error={q.error} onRetry={() => void q.refetch()} /> : q.data.data.length === 0 ? (
        <Empty>{q.data.meta.note ?? "No ticks recorded yet today."}</Empty>
      ) : q.data.data.length < MIN_MINUTES ? (
        <Empty>Only {q.data.data.length} minute{q.data.data.length === 1 ? "" : "s"} of trades have been recorded for this session, too few to draw. Minute data is collected while the market is open, so this fills in during the day.</Empty>
      ) : (
        <IntradayChart bars={q.data.data} day={day} />
      )}
    </Card>
  );
}
