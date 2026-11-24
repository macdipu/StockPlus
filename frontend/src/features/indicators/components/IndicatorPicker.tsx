"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ErrorNotice, Loading } from "@/shared/ui/Notice";
import { useCatalog } from "../hooks/use-catalog";
import type { CatalogEntry } from "../schemas/catalog";
import { formatSpec, parseSpec, searchCatalog } from "../utils/spec";

interface Props {
  /** Spec strings already on the chart ("rsi(14)"): shown as added, and counted so a second one is possible. */
  active: readonly string[];
  onAdd: (spec: string) => void;
  onClose: () => void;
  /** At most this many indicators can be on a chart (the API enforces it too). */
  limit: number;
  /** Why an indicator cannot be used with this data, or null when it can. Such rows are shown but disabled. */
  unavailable?: (entry: CatalogEntry) => string | null;
}

/** A searchable list of every indicator, grouped, with a plain-English line on what each one shows. */
export function IndicatorPicker({ active, onAdd, onClose, limit, unavailable }: Props) {
  const catalog = useCatalog();
  const [query, setQuery] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const counts = useMemo(() => {
    const c = new Map<string, number>();
    for (const s of active) {
      const id = parseSpec(s)?.id;
      if (id) c.set(id, (c.get(id) ?? 0) + 1);
    }
    return c;
  }, [active]);
  const full = active.length >= limit;

  useEffect(() => {
    input.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const results = useMemo(() => (catalog.data ? searchCatalog(catalog.data.indicators, query) : []), [catalog.data, query]);
  const groups = useMemo(() => {
    if (query.trim() || !catalog.data) return [];
    return catalog.data.groups.map((g) => [g, results.filter((e) => e.group === g)] as const).filter(([, list]) => list.length > 0);
  }, [catalog.data, results, query]);

  const row = (e: CatalogEntry, showGroup: boolean) => {
    const n = counts.get(e.id) ?? 0;
    const why = unavailable?.(e) ?? null;
    return (
      <li key={e.id}>
        <button type="button" className="ind-row" disabled={full || why !== null} onClick={() => onAdd(formatSpec(e))} data-indicator={e.id}>
          <span className="ind-name">{e.name}</span>
          <span className="ind-desc small mute">{why ?? e.description}</span>
          <span className="ind-meta small">
            {showGroup ? <span className="mute">{e.group} · </span> : null}
            <span className="mute">{e.placement === "overlay" ? "On the price chart" : "Own panel"}</span>
            {n > 0 ? <b className="ind-added"> · Added{n > 1 ? ` ×${n}` : ""}</b> : null}
          </span>
        </button>
      </li>
    );
  };

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label="Indicators">
        <div className="modal-head">
          <h3>Indicators</h3>
          <button type="button" className="btn ghost small" onClick={onClose} aria-label="Close indicators">Close</button>
        </div>
        <input
          ref={input}
          className="inp modal-search"
          type="search"
          placeholder="Search, e.g. RSI, moving average, volume"
          aria-label="Search indicators"
          autoComplete="off"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {full ? <p className="small dn" style={{ margin: "8px 0 0" }} role="status">A chart can show up to {limit} indicators. Remove one to add another.</p> : null}
        <div className="modal-body">
          {catalog.isPending ? <Loading onRetry={() => void catalog.refetch()} what="Loading indicators" /> : null}
          {catalog.isError ? <ErrorNotice error={catalog.error} onRetry={() => void catalog.refetch()} /> : null}
          {catalog.data && query.trim() ? (
            results.length === 0 ? <p className="mute small">No indicator matches “{query.trim()}”.</p> : <ul className="plain-list">{results.map((e) => row(e, true))}</ul>
          ) : null}
          {catalog.data && !query.trim()
            ? groups.map(([g, list]) => (
                <section key={g} aria-label={g}>
                  <h4 className="ind-group">{g} <span className="mute">({list.length})</span></h4>
                  <ul className="plain-list">{list.map((e) => row(e, false))}</ul>
                </section>
              ))
            : null}
        </div>
      </div>
    </div>
  );
}
