"use client";

import { Card } from "@/shared/ui/Card";
import { Empty, ErrorNotice, Loading } from "@/shared/ui/Notice";
import { useIntraday } from "../hooks/use-stock-queries";
import { IntradayChart } from "./IntradayChart";

/** `day` = the exchange date these minute bars belong to (the session date). */
export function IntradayCard({ symbol, day }: { symbol: string; day: string }) {
  const q = useIntraday(symbol);
  return (
    <Card title="Intraday (1-minute, recorded live)">
      {q.isPending ? <Loading /> : q.isError ? <ErrorNotice error={q.error} /> : q.data.data.length === 0 ? (
        <Empty>{q.data.meta.note ?? "No ticks recorded yet today."}</Empty>
      ) : (
        <IntradayChart bars={q.data.data} day={day} />
      )}
    </Card>
  );
}
