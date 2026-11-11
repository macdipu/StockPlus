"use client";

import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useWatchlist } from "@/features/watchlist";
import { int, num, pct, tone } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { ErrorNotice } from "@/shared/ui/Notice";
import { KeyValueTable } from "@/shared/ui/Stat";
import { toolsApi } from "../services/tools-api";
import { heatColor, parseSymbols } from "../utils/heat";

const daysAgo = (n: number) => new Date(Date.now() - n * 864e5).toISOString().slice(0, 10);

function ReturnCalculator({ defaultSymbol }: { defaultSymbol: string }) {
  const [symbol, setSymbol] = useState(defaultSymbol);
  const [buy, setBuy] = useState(daysAgo(180));
  const [sell, setSell] = useState("");
  const [qty, setQty] = useState("100");
  const [fee, setFee] = useState("0.4");
  const m = useMutation({ mutationFn: toolsApi.returnBetween });
  const go = (e: FormEvent) => {
    e.preventDefault();
    m.mutate({ symbol, buyDate: buy, sellDate: sell, quantity: Number(qty), feePct: Number(fee) });
  };
  const d = m.data?.data;
  return (
    <Card title="Return calculator">
      <form className="row" onSubmit={go}>
        <input className="inp" aria-label="Symbol" style={{ width: 110 }} value={symbol} onChange={(e) => setSymbol(e.target.value)} required />
        <input className="inp" aria-label="Buy date" type="date" value={buy} onChange={(e) => setBuy(e.target.value)} required />
        <input className="inp" aria-label="Sell date (blank = today)" type="date" value={sell} onChange={(e) => setSell(e.target.value)} />
        <input className="inp" aria-label="Quantity" type="number" min="1" step="1" style={{ width: 90 }} value={qty} onChange={(e) => setQty(e.target.value)} />
        <input className="inp" aria-label="Fee % per leg" type="number" min="0" max="5" step="0.05" style={{ width: 80 }} value={fee} onChange={(e) => setFee(e.target.value)} />
        <button className="btn" type="submit" disabled={m.isPending}>Calculate</button>
      </form>
      {m.isError ? <ErrorNotice error={m.error} /> : null}
      {d ? (
        <div data-testid="return-result">
          <KeyValueTable
            rows={[
              ["Bought", `${d.buy_date} @ ${num(d.buy_price)}`],
              ["Sold / now", `${d.sell_date} @ ${num(d.sell_price)}`],
              ["Cost (incl. fees)", num(d.cost)],
              ["Proceeds (after fees)", num(d.proceeds)],
              ["Profit", <b key="p" className={tone(d.profit)}>{num(d.profit)}</b>],
              ["Return", <span key="r"><b className={tone(d.return_pct)}>{pct(d.return_pct, 2)}</b> over {int(d.days)} days</span>],
              ["Annualised", pct(d.annualised_pct, 1)],
            ]}
          />
          <p className="small mute">{d.note}</p>
        </div>
      ) : null}
    </Card>
  );
}

function CsvDownload({ defaultSymbol }: { defaultSymbol: string }) {
  const [symbol, setSymbol] = useState(defaultSymbol);
  const code = symbol.trim();
  return (
    <Card title="Data download">
      <div className="row">
        <input className="inp" aria-label="Symbol to download" style={{ width: 110 }} value={symbol} onChange={(e) => setSymbol(e.target.value)} />
        <a className="btn" href={code ? toolsApi.csvUrl(code) : undefined} aria-disabled={!code} download data-testid="csv-link">
          Download daily OHLCV (CSV)
        </a>
      </div>
      <p className="small mute" style={{ marginBottom: 0 }}>Oldest first. Loads and stores the instrument&apos;s history if it has not been fetched yet.</p>
    </Card>
  );
}

function CorrelationTool({ defaults }: { defaults: string }) {
  const [symbols, setSymbols] = useState(defaults);
  const [days, setDays] = useState("120");
  const m = useMutation({ mutationFn: ({ s, d }: { s: string[]; d: number }) => toolsApi.correlation(s, d) });
  const go = (e: FormEvent) => {
    e.preventDefault();
    m.mutate({ s: parseSymbols(symbols), d: Number(days) });
  };
  const c = m.data?.data;
  return (
    <Card title="Correlation of daily returns">
      <form className="row" onSubmit={go}>
        <input className="inp" aria-label="Symbols (comma separated)" style={{ flex: 1, minWidth: 260 }} value={symbols} onChange={(e) => setSymbols(e.target.value)} />
        <select className="sel" aria-label="Window (sessions)" value={days} onChange={(e) => setDays(e.target.value)}>
          {["60", "120", "250"].map((d) => <option key={d}>{d}</option>)}
        </select>
        <button className="btn" type="submit" disabled={m.isPending}>Compute</button>
      </form>
      {m.isError ? <ErrorNotice error={m.error} /> : null}
      {c ? (
        <div className="heat" role="table" aria-label="Correlation matrix" data-testid="heatmap" style={{ gridTemplateColumns: `90px repeat(${c.symbols.length}, minmax(48px, 1fr))` }}>
          <div className="h" role="row" />
          {c.symbols.map((s) => <div key={`h-${s}`} className="h" role="columnheader">{s}</div>)}
          {c.symbols.flatMap((row, i) => [
            <div key={`r-${row}`} className="h" role="rowheader">{row}</div>,
            ...c.symbols.map((col, j) => {
              const v = c.matrix[i]?.[j] ?? null;
              return <div key={`${row}-${col}`} role="cell" title={`${row} / ${col}`} style={{ background: heatColor(v) }}>{v == null ? "–" : v.toFixed(2)}</div>;
            }),
          ])}
        </div>
      ) : null}
    </Card>
  );
}

export function ToolsPage() {
  const watched = useWatchlist().symbols;
  const first = watched[0] ?? "GP";
  return (
    <>
      <div className="grid2">
        <ReturnCalculator defaultSymbol={first} />
        <CsvDownload defaultSymbol={first} />
      </div>
      <div style={{ marginTop: 16 }}>
        <CorrelationTool defaults={watched.slice(0, 6).join(",") || "GP,BATBC,ROBI"} />
      </div>
    </>
  );
}
