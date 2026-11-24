"use client";

import { int, num } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { Empty, ErrorNotice, Loading } from "@/shared/ui/Notice";
import { useDepth } from "../hooks/use-stock-queries";
import type { DepthSide } from "../schemas/depth";

const clock = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-GB", { timeZone: "Asia/Dhaka", hour12: false });

function Side({ title, side, max, buy }: { title: string; side: DepthSide; max: number; buy: boolean }) {
  return (
    <div>
      <h4 className={`depthtitle ${buy ? "up" : "dn"}`}>{title}</h4>
      <table className="num small depthtable" aria-label={title}>
        <thead>
          <tr><th className="r">Price</th><th className="r">Volume</th><th className="r">Orders</th></tr>
        </thead>
        <tbody>
          {side.levels.length === 0 ? (
            <tr><td colSpan={3} className="mute">{buy ? "No buy orders waiting" : "No sell orders waiting"}</td></tr>
          ) : (
            side.levels.map((l) => (
              <tr key={l.price}>
                <td className={`r ${buy ? "up" : "dn"}`}>{num(l.price)}</td>
                <td
                  className={`r ${buy ? "up" : "dn"}`}
                  style={{
                    backgroundImage: `linear-gradient(color-mix(in srgb, var(${buy ? "--up" : "--dn"}) 22%, transparent), color-mix(in srgb, var(${buy ? "--up" : "--dn"}) 22%, transparent))`,
                    backgroundRepeat: "no-repeat",
                    backgroundSize: `${max ? (l.quantity / max) * 100 : 0}% 100%`,
                    backgroundPosition: buy ? "right" : "left",
                  }}
                >
                  {int(l.quantity)}
                </td>
                <td className="r mute">{l.orders}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
      <p className="small">
        Total {buy ? "buyer" : "seller"} (qty): <b className="num">{int(side.total_quantity)}</b>
        {side.average_price == null ? null : <> @ avg <b className="num">{num(side.average_price)}</b></>}
      </p>
    </div>
  );
}

/** Buyers and sellers waiting at each price, straight from the exchange's depth feed. */
export function DepthCard({ symbol }: { symbol: string }) {
  const q = useDepth(symbol);
  const d = q.data;
  const max = d ? Math.max(1, ...d.buyers.levels.map((l) => l.quantity), ...d.sellers.levels.map((l) => l.quantity)) : 1;
  const total = d ? d.buyers.total_quantity + d.sellers.total_quantity : 0;
  const buyShare = d && total ? (d.buyers.total_quantity / total) * 100 : 0;
  return (
    <Card title="Market depth (DSE)">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="small mute" aria-live="polite">
          {d ? `Fetched at ${clock(d.fetched_at)} Dhaka time · updates every 15 seconds` : ""}
        </span>
        <button type="button" className="btn ghost small" disabled={q.isFetching} onClick={() => void q.refetch()}>
          {q.isFetching ? "Refreshing…" : "Refresh"}
        </button>
      </div>
      {q.isPending ? <Loading onRetry={() => void q.refetch()} what="Loading market depth" /> : null}
      {q.isError ? <ErrorNotice error={q.error} onRetry={() => void q.refetch()} /> : null}
      {d ? (
        <>
          {d.market_open === false ? <p className="small mute">The market is closed; this is the last book DSE published.</p> : null}
          {d.buyers.levels.length === 0 && d.sellers.levels.length === 0 ? (
            <Empty>No orders are waiting for {d.symbol} right now.</Empty>
          ) : (
            <div className="depthgrid">
              <Side title="Buyers" side={d.buyers} max={max} buy />
              <Side title="Sellers" side={d.sellers} max={max} buy={false} />
            </div>
          )}
          {total > 0 ? (
            <div style={{ marginTop: 10 }}>
              <span className="bar" style={{ width: "100%" }} role="img" aria-label={`${Math.round(buyShare)}% of waiting quantity is buying`}>
                <i style={{ width: `${buyShare}%`, background: "var(--up)" }} />
                <i style={{ width: `${100 - buyShare}%`, background: "var(--dn)" }} />
              </span>
              <p className="small mute" style={{ marginBottom: 0 }}>
                {Math.round(buyShare)}% of the waiting quantity is buying
                {d.spread == null ? "" : ` · spread ${num(d.spread)}`}
              </p>
            </div>
          ) : null}
        </>
      ) : null}
    </Card>
  );
}
