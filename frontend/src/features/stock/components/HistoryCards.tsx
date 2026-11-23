"use client";

import { useState } from "react";
import { int, num, pct, tone } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { Empty, ErrorNotice, Loading } from "@/shared/ui/Notice";
import { useCandles } from "../hooks/use-stock-queries";
import { monthlySeasonality, priceTable, weekdaySeasonality, withToday, type SeasonStat, type TodayBar } from "../utils/history";

const WINDOWS = [30, 60, 90, 180, 250] as const;

function Stat({ label, value, cls = "" }: { label: string; value: string; cls?: string }) {
  return (
    <div>
      <div className="small mute">{label}</div>
      <b className={`num ${cls}`}>{value}</b>
    </div>
  );
}

/** Last N working days of daily history with summary stats. */
export function PriceTableCard({ symbol, live }: { symbol: string; live?: TodayBar | null }) {
  const q = useCandles(symbol);
  const [days, setDays] = useState<number>(90);
  const t = q.data ? priceTable(withToday(q.data, live), days) : null;
  return (
    <Card title="Price table">
      <div className="row">
        <span className="small">Last</span>
        <select className="sel" aria-label="Working days" value={days} onChange={(e) => setDays(Number(e.target.value))}>
          {WINDOWS.map((w) => <option key={w} value={w}>{w}</option>)}
        </select>
        <span className="small">working days</span>
      </div>
      {q.isPending ? <Loading /> : q.isError ? <ErrorNotice error={q.error} /> : !t ? <Empty>No daily history stored for {symbol}.</Empty> : (
        <>
          <div className="row" style={{ justifyContent: "space-between", margin: "12px 0" }}>
            <Stat label="Avg price" value={num(t.avgPrice, 1)} />
            <Stat label="Max price" value={num(t.maxPrice, 1)} />
            <Stat label="Min price" value={num(t.minPrice, 1)} />
            <Stat label="Change" value={num(t.change, 1)} cls={tone(t.change)} />
            <Stat label="Avg volume" value={int(Math.round(t.avgVolume))} />
            <Stat label="Max volume" value={int(t.maxVolume)} />
            <Stat label="Min volume" value={int(t.minVolume)} />
            <Stat label="Change (%)" value={pct(t.changePct, 1)} cls={tone(t.changePct)} />
          </div>
          <div className="tablewrap">
            <table className="num small">
              <thead>
                <tr><th>Date</th><th>Close</th><th>Volume</th><th>Change</th><th>Ch (%)</th><th>Trades</th><th>Open</th><th>High</th><th>Low</th></tr>
              </thead>
              <tbody>
                {t.rows.map((r) => (
                  <tr key={r.day}>
                    <td>{r.day}</td>
                    <td className={tone(r.change)}>{num(r.close)}</td>
                    <td>{int(r.volume)}</td>
                    <td className={tone(r.change)}>{num(r.change)}</td>
                    <td className={tone(r.changePct)}>{pct(r.changePct, 2)}</td>
                    <td>{r.trades == null ? "–" : int(r.trades)}</td>
                    <td>{num(r.open)}</td>
                    <td>{num(r.high)}</td>
                    <td>{num(r.low)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}

function SeasonTable({ title, note, rows }: { title: string; note: string; rows: SeasonStat[] }) {
  const max = Math.max(1, ...rows.map((r) => Math.abs(r.avgPct)));
  return (
    <Card title={title}>
      <p className="small mute" style={{ marginTop: 0 }}>{note}</p>
      <div className="tablewrap">
        <table className="num small">
          <thead><tr><th></th><th>Avg return</th><th></th><th>Up</th><th>Samples</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label}>
                <td>{r.label}</td>
                <td className={r.n ? tone(r.avgPct) : "mute"}>{r.n ? pct(r.avgPct, 2) : "–"}</td>
                <td style={{ width: "40%" }}>
                  {r.n ? (
                    <span className="bar" style={{ display: "block", height: 8 }}>
                      <i style={{ width: `${(Math.abs(r.avgPct) / max) * 100}%`, background: r.avgPct >= 0 ? "var(--up)" : "var(--dn)" }} />
                    </span>
                  ) : null}
                </td>
                <td>{r.n ? `${Math.round(r.winPct)}%` : "–"}</td>
                <td>{r.n}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/** How the share has tended to move by calendar month and by weekday, from its stored daily history. */
export function SeasonalityCards({ symbol }: { symbol: string }) {
  const q = useCandles(symbol);
  if (q.isPending) return <Card title="Seasonality"><Loading /></Card>;
  if (q.isError) return <Card title="Seasonality"><ErrorNotice error={q.error} /></Card>;
  if (q.data.length < 40) return <Card title="Seasonality"><Empty>Not enough history yet to see a pattern.</Empty></Card>;
  const first = q.data[0]!.day;
  return (
    <>
      <SeasonTable
        title="By month"
        note={`Average month-end to month-end return since ${first}. "Up" is the share of those months that closed higher. Past patterns do not predict the future.`}
        rows={monthlySeasonality(q.data)}
      />
      <SeasonTable title="By weekday" note="Average close-to-close return on each trading weekday." rows={weekdaySeasonality(q.data)} />
    </>
  );
}
