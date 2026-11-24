"use client";

import { routes } from "@/shared/lib/navigation";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Card } from "@/shared/ui/Card";
import { DataTable } from "@/shared/ui/DataTable";
import { columnsFor, symbolHref } from "@/shared/ui/columns";
import { Chips } from "@/shared/ui/Chips";
import { ErrorNotice, Loading } from "@/shared/ui/Notice";
import { useDataTable } from "../hooks/use-data-table";
import type { DataTab } from "../services/data-api";
import { downloadCsv, toCsv } from "../utils/csv";

type Row = Record<string, unknown> & { symbol?: string };

const TABS = [
  { key: "matrix", label: "Data matrix (fundamentals)" },
  { key: "ta", label: "TA values" },
] as const;

export function DataPage() {
  const sector = useSearchParams().get("sector");
  const [tab, setTab] = useState<DataTab>("matrix");
  const q = useDataTable(tab, sector);
  const rows = (q.data ?? []) as Row[];
  const keys = rows[0] ? Object.keys(rows[0]).filter((k) => k !== "name" || tab === "matrix") : [];

  return (
    <Card label="Data">
      <div className="row">
        <Chips<DataTab> label="Table" options={TABS} value={tab} onChange={setTab} />
        <span className="mute small">
          {sector ? <>Sector: <b>{sector}</b> · <Link href={routes.findTable()}>Show all sectors</Link></> : "All sectors"}
        </span>
        <button
          className="btn ghost small"
          type="button"
          style={{ marginLeft: "auto" }}
          disabled={rows.length === 0}
          onClick={() => downloadCsv(`dse-${tab === "matrix" ? "data-matrix" : "ta-values"}.csv`, toCsv(rows, keys))}
        >
          Export CSV
        </button>
      </div>
      {q.isPending ? <Loading onRetry={() => void q.refetch()} /> : q.isError ? <ErrorNotice error={q.error} onRetry={() => void q.refetch()} /> : (
        <DataTable<Row>
          caption={tab === "matrix" ? "Fundamentals and valuation for every instrument" : "Technical indicator values for every instrument"}
          rows={rows}
          rowKey={(r) => String(r.symbol)}
          rowHref={symbolHref}
          columns={columnsFor<Row>(keys, rows[0])}
          defaultSort={{ key: "symbol", desc: false }}
        />
      )}
    </Card>
  );
}
