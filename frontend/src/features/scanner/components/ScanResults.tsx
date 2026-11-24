"use client";

import type { UseQueryResult } from "@tanstack/react-query";
import { Card } from "@/shared/ui/Card";
import { DataTable } from "@/shared/ui/DataTable";
import { columnsFor, symbolHref } from "@/shared/ui/columns";
import { ErrorNotice, Loading } from "@/shared/ui/Notice";
import type { Fields, ScanResult, ScanRow } from "../schemas/scanner";

interface Props {
  title: string;
  description?: string;
  query: UseQueryResult<ScanResult>;
  fields: Fields | undefined;
  idle?: string;
}

export function ScanResults({ title, description, query, fields, idle }: Props) {
  return (
    <Card title={title}>
      {description ? <p className="small mute">{description}</p> : null}
      {query.isPending && idle ? <p className="notice">{idle}</p> : query.isPending ? <Loading onRetry={() => void query.refetch()} /> : query.isError ? <ErrorNotice error={query.error} onRetry={() => void query.refetch()} /> : (() => {
        const { data, meta } = query.data;
        const columns = columnsFor<ScanRow>(fields?.default_columns ?? ["symbol", "ltp", "change_pct"], data[0]);
        return (
          <>
            <p className="small mute" data-testid="scan-meta">
              {meta.matched} of {meta.scanned} instruments · {meta.live ? "live session" : "last completed session"} · universe v
              {meta.universe_version} · trade time {meta.trade_time ?? "–"} · refreshes on every tick
            </p>
            <DataTable<ScanRow>
              caption={title}
              rows={data}
              rowKey={(r) => String(r.symbol)}
              rowHref={(r) => symbolHref({ symbol: typeof r.symbol === "string" ? r.symbol : null })}
              columns={columns}
              empty="No instruments match."
            />
          </>
        );
      })()}
    </Card>
  );
}
