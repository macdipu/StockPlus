"use client";

import type { UseQueryResult } from "@tanstack/react-query";
import { useMemo, useState, type ReactNode } from "react";
import { PriceChart } from "@/features/chart";
import { FreshnessBar } from "@/features/universe";
import { routes } from "@/shared/lib/navigation";
import { Card } from "@/shared/ui/Card";
import { DataTable } from "@/shared/ui/DataTable";
import { columnsFor, symbolHref } from "@/shared/ui/columns";
import { ErrorNotice, Loading } from "@/shared/ui/Notice";
import { useMovers, usePe, useRange52, useSectors } from "../hooks/use-market-queries";
import type { RangeRow, SectorRow } from "../schemas/market";
import { MarketSummary } from "./MarketSummary";
import type { Quote } from "@/shared/api";

function Async<T>({ q, children }: { q: UseQueryResult<T>; children: (data: T) => ReactNode }) {
  if (q.isPending) return <Loading onRetry={() => void q.refetch()} />;
  if (q.isError) return <ErrorNotice error={q.error} onRetry={() => void q.refetch()} />;
  return <>{children(q.data)}</>;
}

const SECTOR_COLS = ["sector", "instruments", "advanced", "declined", "avg_change_pct", "turnover_mn", "turnover_share_pct", "median_pe", "avg_rsi", "ret_1m"];
const MOVER_COLS = ["symbol", "ltp", "percent", "value_mn"];
const RANGE_COLS = ["symbol", "ltp", "low_52w", "high_52w", "range_position_pct"];

function Movers({ title, by }: { title: string; by: "gainers" | "losers" | "value" }) {
  const q = useMovers(by);
  return (
    <Card title={title}>
      <Async q={q}>
        {(rows) => (
          <DataTable<Quote>
            caption={title}
            rows={rows}
            rowKey={(r) => r.symbol}
            rowHref={symbolHref}
            columns={columnsFor<Quote>(MOVER_COLS, rows[0] as unknown as Record<string, unknown>)}
          />
        )}
      </Async>
    </Card>
  );
}

const INDICES = [
  { code: "DSEX", label: "DSEX", hint: "The broad index of the Dhaka Stock Exchange" },
  { code: "DS30", label: "DS30", hint: "The 30 largest, most liquid companies" },
  { code: "DSES", label: "DSES", hint: "Shariah-compliant companies" },
] as const;

/** The market's own chart: a DSE index with the same timeframes, styles and indicators as a share. */
function IndexChart() {
  const [code, setCode] = useState<(typeof INDICES)[number]["code"]>("DSEX");
  return (
    <Card title="Market index">
      <div className="seg" role="group" aria-label="Index" style={{ marginBottom: 10 }}>
        {INDICES.map((i) => (
          <button key={i.code} type="button" aria-pressed={code === i.code} title={i.hint} className={code === i.code ? "on" : ""} onClick={() => setCode(i.code)}>
            {i.label}
          </button>
        ))}
      </div>
      <PriceChart key={code} symbol={code} scope="market" />
    </Card>
  );
}

export function MarketPage() {
  const sectors = useSectors();
  const pe = usePe();
  const range = useRange52();

  const peRows = useMemo(() => {
    if (!pe.data) return [];
    const d = pe.data;
    return [
      { name: "Market", ...d.market },
      ...Object.entries(d.by_category).map(([k, v]) => ({ name: `Category ${k}`, ...v })),
      ...Object.entries(d.by_sector).map(([k, v]) => ({ name: k, ...v })),
    ];
  }, [pe.data]);

  return (
    <>
      <FreshnessBar />
      <MarketSummary />
      <IndexChart />
      <Card title="Sectors">
        <Async q={sectors}>
          {(rows) => (
            <DataTable<SectorRow>
              caption="Sector performance"
              rows={rows}
              rowKey={(r) => r.sector}
              rowHref={(r) => routes.findTable(r.sector)}
              defaultSort={{ key: "turnover_mn", desc: true }}
              columns={columnsFor<SectorRow>(SECTOR_COLS, rows[0] as unknown as Record<string, unknown>)}
            />
          )}
        </Async>
        <p className="small mute" style={{ marginBottom: 0 }}>Click a sector to see its fundamentals in the Data tab.</p>
      </Card>
      <div className="cols3">
        <Movers title="Top gainers" by="gainers" />
        <Movers title="Top losers" by="losers" />
        <Movers title="Most active (value)" by="value" />
      </div>
      <div className="grid2">
        <Card title="P/E — market, category and sector">
          <Async q={pe}>
            {(d) => (
              <>
                <DataTable
                  caption="P/E by group"
                  rows={peRows}
                  rowKey={(r) => r.name}
                  columns={columnsFor<{ name: string }>(["name", "instruments", "median_pe", "weighted_pe"], peRows[0] as unknown as Record<string, unknown>)}
                />
                <p className="small mute">{d.note}</p>
              </>
            )}
          </Async>
        </Card>
        <Card title="52-week range">
          <Async q={range}>
            {(rows) => (
              <DataTable<RangeRow>
                caption="Where each equity sits in its 52-week range"
                rows={rows}
                rowKey={(r) => r.symbol}
                rowHref={symbolHref}
                columns={columnsFor<RangeRow>(RANGE_COLS, rows[0] as unknown as Record<string, unknown>)}
              />
            )}
          </Async>
        </Card>
      </div>
    </>
  );
}
