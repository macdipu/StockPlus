"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useWatchlist } from "@/features/watchlist";
import { num, pct, tone } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { ErrorNotice, Loading } from "@/shared/ui/Notice";
import { DEFAULT_FILTERS, useSavedFilters } from "../hooks/use-saved-filters";
import { usePicks, useRescan } from "../hooks/use-picks";
import { BUCKETS, type Bucket, type Pick, type PickFilters } from "../schemas/picks";

const BUCKET_LABEL: Record<Bucket, string> = {
  buy_zone: "Buy zone now",
  wait_pullback: "Wait for a pullback",
  watch: "Watch",
  avoid: "Avoid for now",
};

function useNow(everyMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(t);
  }, [everyMs]);
  return now;
}

function ago(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s ago`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m ago`;
}

function ScoreBar({ v, label }: { v: number; label: string }) {
  const color = v >= 65 ? "var(--up)" : v >= 45 ? "#d97706" : "var(--dn)";
  return (
    <span title={`${label} ${v}/100`} className="small">
      <span className="bar" style={{ width: 54, height: 6, display: "inline-flex", verticalAlign: "middle" }}>
        <i style={{ width: `${v}%`, background: color }} />
      </span>{" "}
      <span className="score">{v}</span>
    </span>
  );
}

function SectorPicker({ sectors, f, onChange }: { sectors: readonly string[]; f: PickFilters; onChange: (f: PickFilters) => void }) {
  const [mode, setMode] = useState<"exclude" | "include">("exclude");
  const list = mode === "exclude" ? f.exclude : f.include;
  const toggle = (s: string) => {
    const next = list.includes(s) ? list.filter((x) => x !== s) : [...list, s];
    onChange(mode === "exclude" ? { ...f, exclude: next, include: f.include.filter((x) => x !== s) } : { ...f, include: next, exclude: f.exclude.filter((x) => x !== s) });
  };
  return (
    <div>
      <div className="row">
        <span className="small mute">Sectors:</span>
        <div className="seg" role="tablist" aria-label="Sector filter mode">
          <button type="button" role="tab" aria-selected={mode === "exclude"} className={mode === "exclude" ? "on" : ""} onClick={() => setMode("exclude")}>Leave out</button>
          <button type="button" role="tab" aria-selected={mode === "include"} className={mode === "include" ? "on" : ""} onClick={() => setMode("include")}>Only these</button>
        </div>
        <button type="button" className="btn ghost small" onClick={() => onChange({ ...f, include: [], exclude: [] })}>All sectors</button>
      </div>
      <div className="chips" role="group" aria-label={mode === "exclude" ? "Sectors to leave out" : "Sectors to keep"}>
        {sectors.map((s) => {
          const on = list.includes(s);
          const other = mode === "exclude" ? f.include.includes(s) : f.exclude.includes(s);
          return (
            <button key={s} type="button" aria-pressed={on} className={`chip ${on ? "on" : ""}`} onClick={() => toggle(s)} style={mode === "exclude" && on ? { textDecoration: "line-through" } : other ? { opacity: 0.5 } : undefined}>
              {s}
            </button>
          );
        })}
      </div>
      <p className="small mute" style={{ marginBottom: 0 }}>
        {f.include.length ? `Only: ${f.include.join(", ")}. ` : ""}
        {f.exclude.length ? `Leaving out: ${f.exclude.join(", ")}.` : f.include.length ? "" : "All sectors included."}
      </p>
    </div>
  );
}

function Row({ p, watched, onWatch }: { p: Pick; watched: boolean; onWatch: () => void }) {
  return (
    <tr data-symbol={p.symbol} data-bucket={p.bucket}>
      <td>
        <Link href={`/stock/${p.symbol}`}><b>{p.symbol}</b></Link>
        <div className="small mute" style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.name ?? ""}</div>
      </td>
      <td className="small">{p.sector ?? "–"} <span className="mute">{p.category ?? ""}</span></td>
      <td className="r num">{num(p.ltp)}<div className={`small ${tone(p.change_pct)}`}>{pct(p.change_pct, 2)}</div></td>
      <td className="r num">{num(p.pe, 1)}</td>
      <td className="r num">{num(p.pb, 2)}</td>
      <td className="r num">{p.dividend_yield_pct == null ? "–" : `${num(p.dividend_yield_pct, 1)}%`}</td>
      <td className="r num">{num(p.rsi14, 0)}</td>
      <td><ScoreBar v={p.value_score} label="Value" /></td>
      <td><ScoreBar v={p.entry_score} label="Entry" /></td>
      <td className="r num"><b>{num(p.pick_score, 0)}</b></td>
      <td><span className={`bucket ${p.bucket}`}>{p.bucket_label}</span></td>
      <td className="small" style={{ minWidth: 220 }}>
        {p.reasons.length ? <span className="up">{p.reasons.slice(0, 3).join("; ")}</span> : null}
        {p.warnings.length ? <div className="dn">{p.warnings.slice(0, 2).join("; ")}</div> : null}
      </td>
      <td>
        <button type="button" className="btn ghost small" disabled={watched} onClick={onWatch} aria-label={`Add ${p.symbol} to watchlist`}>
          {watched ? "Watching" : "+ Watch"}
        </button>
      </td>
    </tr>
  );
}

/** A watch list built by analysing every share: value for money + entry timing, with sector filters. */
export function PicksPage() {
  const [f, setF] = useSavedFilters();
  const q = usePicks(f);
  const w = useWatchlist();
  const [shown, setShown] = useState<Bucket | "all">("all");
  const rows = useMemo(() => (q.data?.data ?? []).filter((r) => shown === "all" || r.bucket === shown), [q.data, shown]);
  const meta = q.data?.meta;
  const rescan = useRescan(meta?.universe_version);
  const now = useNow();
  const addAll = () => {
    for (const r of rows.filter((x) => x.bucket === "buy_zone").slice(0, 15)) if (!w.has(r.symbol)) w.add(r.symbol);
  };
  return (
    <>
      <Card title="Market picks: value for money and entry timing">
        <p className="small" style={{ marginTop: 0 }}>
          Every share is scored twice from the latest data. <b>Value</b> looks at P/E, price/book, dividend yield, Graham number and sponsor holding.
          <b> Entry</b> looks at RSI, trend, place in the 52-week range, MACD, the last candle and volume. Then each share is put in a bucket.
          Not investment advice.
        </p>
        {meta ? <SectorPicker sectors={meta.sectors} f={f} onChange={setF} /> : null}
        <div className="row" style={{ marginTop: 10 }}>
          <select className="sel" aria-label="Category" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>
            <option value="">All categories</option>
            <option value="A">A only</option>
            <option value="A,B">A and B</option>
            <option value="B">B only</option>
            <option value="Z">Z only</option>
          </select>
          <input className="inp" style={{ width: 170 }} inputMode="decimal" placeholder="Min turnover (mn Tk)" aria-label="Minimum turnover today, million Tk" value={f.minValueMn} onChange={(e) => setF({ ...f, minValueMn: e.target.value.replace(/[^\d.]/g, "") })} />
          <button type="button" className="btn ghost small" onClick={() => setF(DEFAULT_FILTERS)}>Reset filters</button>
          {meta ? <span className="small mute">{meta.live ? "Live session" : "Last close"}{meta.trade_time ? ` · market ${meta.trade_time}` : ""} · {meta.count} shares</span> : null}
        </div>
      </Card>
      <Card label="Picks">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div className="seg" role="tablist" aria-label="Bucket">
            <button type="button" role="tab" aria-selected={shown === "all"} className={shown === "all" ? "on" : ""} onClick={() => setShown("all")}>All</button>
            {BUCKETS.map((b) => (
              <button key={b} type="button" role="tab" aria-selected={shown === b} className={shown === b ? "on" : ""} onClick={() => setShown(b)}>
                {BUCKET_LABEL[b]} {meta ? <span className="mute">({meta.counts[b] ?? 0})</span> : null}
              </button>
            ))}
          </div>
          <div className="row">
            {meta ? (
              <span className="small mute" title={`Analysed ${new Date(meta.built_at_ms).toLocaleString()} (took ${meta.build_ms} ms). Refreshes automatically.`}>
                Updated {ago(now - meta.built_at_ms)}
              </span>
            ) : null}
            {rescan.isError ? <span className="small" style={{ color: "var(--dn)" }}>Rescan failed</span> : null}
            <button type="button" className="btn ghost small" disabled={rescan.isPending} onClick={() => rescan.mutate()} title="Pull fresh data from DSE and re-score every share">
              {rescan.isPending ? "Rescanning…" : "Rescan now"}
            </button>
            <button type="button" className="btn small" onClick={addAll} title="Adds the top 15 shares in the buy zone to your watchlist">+ Watch top buy-zone picks</button>
          </div>
        </div>
        {q.isPending ? <Loading what="Scoring every share" /> : null}
        {q.isError ? <ErrorNotice error={q.error} /> : null}
        {q.data ? (
          <div className="tablewrap">
            <table data-agent="picks">
              <thead>
                <tr>
                  <th>Share</th><th>Sector</th><th className="r">Price</th><th className="r">P/E</th><th className="r">P/B</th><th className="r">Yield</th><th className="r">RSI</th>
                  <th>Value</th><th>Entry</th><th className="r">Score</th><th>Bucket</th><th>Why</th><th />
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => <Row key={p.symbol} p={p} watched={w.has(p.symbol)} onWatch={() => w.add(p.symbol)} />)}
                {rows.length === 0 ? <tr><td colSpan={13} className="mute">No shares match these filters.</td></tr> : null}
              </tbody>
            </table>
          </div>
        ) : null}
      </Card>
    </>
  );
}
