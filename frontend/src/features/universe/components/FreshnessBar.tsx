"use client";

import { useEffect, useState } from "react";
import { ago, useNow, useRescan, useUniverseStatus } from "../hooks/use-universe";

/** "Updated 12s ago · market data from …": how fresh the market-wide analysis is. */
export function FreshnessLabel() {
  const q = useUniverseStatus();
  const now = useNow();
  const s = q.data;
  if (!s?.built_at_ms) return <span className="small mute">{q.isError ? "Could not read the analysis status." : "Waiting for the first analysis…"}</span>;
  return (
    <span className="small mute" role="status" title={`Analysed ${new Date(s.built_at_ms).toLocaleString()} (took ${s.build_ms ?? 0} ms). Refreshes automatically.`}>
      Updated {ago(now - s.built_at_ms)}{s.trade_time ? ` · market data from ${s.trade_time}` : ""}
    </span>
  );
}

/** Pull fresh data from DSE, rebuild the analysis, and refetch the page. */
export function RescanButton() {
  const rescan = useRescan();
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (!done) return;
    const t = setTimeout(() => setDone(false), 4_000);
    return () => clearTimeout(t);
  }, [done]);
  return (
    <>
      <span className="small up" role="status" aria-live="polite">{done ? "Rescanned. Showing the latest data." : ""}</span>
      {rescan.isError ? <span className="small dn">Rescan failed. Try again in a moment.</span> : null}
      <button type="button" className="btn ghost small" disabled={rescan.isPending} onClick={() => { setDone(false); rescan.mutate(undefined, { onSuccess: () => setDone(true) }); }} title="Pull fresh data from DSE and re-score every share">
        {rescan.isPending ? "Rescanning…" : "Rescan now"}
      </button>
    </>
  );
}

export function FreshnessBar() {
  return (
    <div className="row freshness">
      <FreshnessLabel />
      <RescanButton />
    </div>
  );
}
