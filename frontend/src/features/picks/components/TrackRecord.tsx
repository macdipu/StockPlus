"use client";

import { useState } from "react";
import { pct, tone } from "@/shared/lib/format";
import { useTrackRecord } from "../hooks/use-picks";
import { BUCKETS, type Bucket } from "../schemas/picks";

const LABEL: Record<Bucket, string> = {
  buy_zone: "Buy zone now",
  wait_pullback: "Wait for a pullback",
  watch: "Watch",
  avoid: "Avoid for now",
};

/** What each bucket went on to do in a replay of past sessions. Collapsed by default; the limits sit beside the numbers. */
export function TrackRecord() {
  const q = useTrackRecord();
  const [horizon, setHorizon] = useState<string | null>(null);
  const t = q.data;
  if (!t) return null;
  const h = horizon ?? String(t.horizons.at(-1) ?? "");
  const rows = t.by_bucket[h] ?? {};
  const entry = t.rank_correlation[h]?.entry_score;
  return (
    <details className="card trackrecord">
      <summary><b>How have these buckets done before?</b> <span className="small mute">A replay of past sessions, not a promise</span></summary>
      <p className="small">
        We re-scored every share as it would have looked on {t.days} past sessions ({t.from} to {t.to}, {t.shares} shares) and checked what happened next.
        &ldquo;Against the market&rdquo; is the return minus the average share on the same day.
      </p>
      <div className="seg" role="group" aria-label="Sessions ahead" style={{ marginBottom: 10 }}>
        {t.horizons.map((x) => (
          <button key={x} type="button" aria-pressed={h === String(x)} className={h === String(x) ? "on" : ""} onClick={() => setHorizon(String(x))}>
            {x} sessions later
          </button>
        ))}
      </div>
      <div className="tablewrap">
        <table className="small">
          <thead>
            <tr><th>Bucket</th><th className="r">Signals</th><th className="r">Average return</th><th className="r">Against the market</th><th className="r">Beat the market</th></tr>
          </thead>
          <tbody>
            {BUCKETS.map((b) => {
              const s = rows[b];
              return s && s.n > 0 ? (
                <tr key={b}>
                  <td>{LABEL[b]}</td>
                  <td className="r num">{s.n.toLocaleString("en-US")}</td>
                  <td className={`r num ${tone(s.mean_pct)}`}>{pct(s.mean_pct, 2)}</td>
                  <td className={`r num ${tone(s.excess_pct)}`}><b>{pct(s.excess_pct, 2)}</b></td>
                  <td className="r num">{s.beat_market_pct == null ? "–" : `${Math.round(s.beat_market_pct)}%`}</td>
                </tr>
              ) : null;
            })}
          </tbody>
        </table>
      </div>
      {entry?.share_of_days_positive_pct != null ? (
        <p className="small">
          Higher entry-timing scores were followed by higher returns on {Math.round(entry.share_of_days_positive_pct)}% of the replayed days.
        </p>
      ) : null}
      <ul className="plain small mute">
        {t.notes.map((n) => <li key={n}>{n}</li>)}
      </ul>
      <p className="small mute">Updated {t.generated_at}. For research only, not investment advice.</p>
    </details>
  );
}
