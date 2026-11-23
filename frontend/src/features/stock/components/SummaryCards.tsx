import type { Company } from "@/features/company";
import { crore, num, pct } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { SignalPill } from "@/shared/ui/Pill";
import type { Analysis } from "../schemas/analysis";
import { dividendYield, edgeReading } from "../utils/reading";
import { sparkPoints } from "../utils/strength";
import { avgTurnoverMn, buyZone, HOW_RATED, type Summary, type TileReading, type Tone } from "../utils/summary";

const TONE_CLASS: Record<Tone, string> = { up: "up", dn: "dn", warn: "warn", mute: "mute" };

const place = (v: number, lo: number, hi: number) => (hi > lo ? Math.min(100, Math.max(0, ((v - lo) / (hi - lo)) * 100)) : 50);

/** Where the price sits in its 52-week range, with the buy zone, stop and target marked on the same bar. */
function RangeBar({ a }: { a: Analysis }) {
  const { low_52w: lo, high_52w: hi } = a.levels;
  const price = a.price.ltp;
  if (price == null || !(hi > lo)) return null;
  const plan = a.setup.plan;
  const zone = buyZone(a);
  const [z1, z2] = [zone.low, zone.high];
  const up = ((price - lo) / lo) * 100;
  const down = ((hi - price) / hi) * 100;
  const label = `Price ${num(price)} is ${num(up, 0)}% above its 52-week low of ${num(lo)} and ${num(down, 0)}% below its high of ${num(hi)}.`;
  return (
    <div className="rangebar">
      <div className="rangetrack" role="img" aria-label={label}>
        <i className="rzone" style={{ left: `${place(z1, lo, hi)}%`, width: `${Math.max(1, place(z2, lo, hi) - place(z1, lo, hi))}%` }} title={`Buy zone ${num(z1)}–${num(z2)}`} />
        <i className="rtick dn" style={{ left: `${place(plan.stop, lo, hi)}%` }} title={`Stop ${num(plan.stop)}`} />
        <i className="rtick up" style={{ left: `${place(plan.target, lo, hi)}%` }} title={`Target ${num(plan.target)}`} />
        <b className="rprice" style={{ left: `${place(price, lo, hi)}%` }} title={`Price ${num(price)}`} />
      </div>
      <div className="rangeends small num"><span>{num(lo)} <span className="mute">52-week low</span></span><span><span className="mute">52-week high</span> {num(hi)}</span></div>
      <div className="small mute">
        <span className="legend-dot zone" /> buy zone {num(z1)}–{num(z2)} · <span className="legend-dot stop" /> stop {num(plan.stop)} · <span className="legend-dot target" /> target {num(plan.target)}
      </div>
    </div>
  );
}

/** What the share is and how it stands today, before any opinion. */
export function SnapshotCard({ analysis: a, company }: { analysis: Analysis; company: Company | undefined }) {
  const f = a.fundamentals;
  const dy = dividendYield(a);
  const turnover = avgTurnoverMn(a);
  const rating = company?.profile.credit_rating?.long_term ?? null;
  const facts: Array<[string, string, string?]> = [
    ["Market value", f.market_cap == null ? "–" : crore(f.market_cap)],
    ["P/E (price ÷ yearly earnings)", f.pe == null ? "–" : num(f.pe, 1)],
    ["Dividend yield", dy.value == null ? "–" : `${num(dy.value, 1)}%`, dy.basis],
    ["Freely traded shares", f.free_float_pct == null ? "–" : `${num(f.free_float_pct, 0)}%`],
    ["Typical daily turnover", turnover == null ? "–" : `Tk ${num(turnover, 1)} mn`],
    ["Credit rating", rating ?? "–"],
  ];
  return (
    <Card title="At a glance">
      <p className="small mute" style={{ marginTop: 0 }}>
        {[f.sector, f.category ? `Category ${f.category}` : null, a.price.market_open ? "Market open" : "Market closed", a.as_of ? `as of ${a.as_of}` : null].filter(Boolean).join(" · ")}
      </p>
      <RangeBar a={a} />
      <div className="kv" style={{ marginTop: 12 }}>
        {facts.map(([label, value, hint]) => (
          <div key={label} title={hint}>
            <span>{label}</span>
            <b className="num">{value}</b>
          </div>
        ))}
      </div>
    </Card>
  );
}

/** The one-sentence reading, the action it points to, and the model's own signal. */
export function VerdictCard({ analysis: a, summary }: { analysis: Analysis; summary: Summary }) {
  return (
    <Card label="Our reading">
      <div className="hero" style={{ alignItems: "center", gap: 16 }}>
        <div style={{ textAlign: "center" }}>
          <SignalPill action={a.signal.action} />
          <div className="small mute" style={{ marginTop: 4 }}>short-term signal</div>
        </div>
        <div style={{ flex: 1, minWidth: 240 }}>
          <p style={{ margin: "0 0 4px", fontSize: 16 }}><b>{summary.verdict}</b></p>
          <p style={{ margin: 0 }}>{summary.actionLine}</p>
        </div>
      </div>
    </Card>
  );
}

/** A tiny trend line: the shape of earnings over the years, with the last point marked. */
function Spark({ trend }: { trend: NonNullable<TileReading["trend"]> }) {
  const W = 220;
  const H = 36;
  const pts = sparkPoints(trend.values, W, H);
  const last = pts.split(" ").at(-1)?.split(",") ?? [];
  const first = trend.values[0];
  const end = trend.values.at(-1);
  return (
    <div className="spark">
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-label={`${trend.label}, ${trend.first} to ${trend.last}: ${num(first)} to ${num(end)}`}>
        <polyline points={pts} fill="none" stroke="var(--brand)" strokeWidth="2" strokeLinejoin="round" />
        <circle cx={last[0]} cy={last[1]} r="3.5" fill="var(--brand)" />
      </svg>
      <span className="small mute">{trend.label}, {trend.first} to {trend.last}: {num(first)} → {num(end)}</span>
    </div>
  );
}

function Tile({ t }: { t: TileReading }) {
  return (
    <section className="card tile" aria-label={t.title}>
      <div className="tilehead">
        <h3 className="card-title" style={{ margin: 0 }}>{t.title}</h3>
        <span className={`rating ${TONE_CLASS[t.tone]}`}>{t.rating}</span>
      </div>
      {t.facts.length ? (
        <dl className="tilefacts num small">
          {t.facts.map((f) => (
            <div key={f.label}><dt className="mute">{f.label}</dt><dd>{f.value}</dd></div>
          ))}
        </dl>
      ) : null}
      {t.trend ? <Spark trend={t.trend} /> : null}
      {t.evidence.length ? (
        <ul className="plain small tileevidence">
          {t.evidence.map((e) => (
            <li key={e.text} className={e.points > 0 ? "up" : e.points < 0 ? "dn" : "mute"}>
              <span aria-hidden="true">{e.points > 0 ? "✓" : e.points < 0 ? "✗" : "·"}</span> <span className="ink">{e.text}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="small mute" style={{ marginBottom: 0 }}>{t.key === "risk" ? "No major risk flags in the data." : "Nothing to base a reading on yet."}</p>
      )}
    </section>
  );
}

/** Business quality, value, timing and risk: a rating word, the numbers behind it, and the rules that applied. */
export function Scorecard({ summary }: { summary: Summary }) {
  return (
    <>
      <div className="scorecard">{summary.tiles.map((t) => <Tile key={t.key} t={t} />)}</div>
      <details className="howrated small">
        <summary>How these ratings are reached</summary>
        <ul className="plain">{HOW_RATED.map((h) => <li key={h}>{h}</li>)}</ul>
      </details>
    </>
  );
}

export function ReasonsCard({ summary }: { summary: Summary }) {
  return (
    <Card title="The case for and against">
      <div className="grid2 small">
        <div>
          <b className="up">For</b>
          <ul className="plain">{summary.reasonsFor.length ? summary.reasonsFor.map((r) => <li key={r}>{r}</li>) : <li className="mute">Nothing stands out in its favour.</li>}</ul>
        </div>
        <div>
          <b className="dn">Against</b>
          <ul className="plain">{summary.reasonsAgainst.length ? summary.reasonsAgainst.map((r) => <li key={r}>{r}</li>) : <li className="mute">Nothing stands out against it.</li>}</ul>
        </div>
      </div>
    </Card>
  );
}

/** The plan in four numbers and one honest sentence about the odds; the full plan is below the chart. */
export function PlanSummaryCard({ analysis: a }: { analysis: Analysis }) {
  const p = a.setup.plan;
  const zone = buyZone(a);
  const sim = a.probability.similar_setups;
  const edge = edgeReading(sim.p_target_first, a.probability.all_days_baseline.p_target_first, sim.n, a.probability.reliable);
  return (
    <Card title="If you act">
      <div className="kv">
        <div><span>Buy zone</span><b className="num">{num(zone.low)}–{num(zone.high)}</b></div>
        <div><span>Exit if it closes below</span><b className="num dn">{num(p.stop)}</b></div>
        <div><span>Take profit near</span><b className="num up">{num(p.target)}</b></div>
        <div><span>Reward per unit of risk</span><b className={`num ${p.rr_ok ? "up" : "dn"}`}>{num(p.rr)}</b></div>
      </div>
      <p className="small" style={{ marginBottom: 0 }}>
        Target {pct(p.reward_pct, 1)} away, stop {pct(-p.risk_pct, 1)} away. <span className={edge.tone}>{edge.text}</span> The full plan is under the chart.
      </p>
    </Card>
  );
}

/** Dividends, meetings and the latest company news. */
export function ComingUpCard({ company }: { company: Company | undefined }) {
  const e = company?.events;
  const lines: string[] = [];
  if (e?.declared_dividend_pct != null) lines.push(`${num(e.declared_dividend_pct, 0)}% ${e.declared_dividend_type ?? ""} dividend declared${e.declaration_date ? ` on ${e.declaration_date}` : ""}.`.replace("  ", " "));
  lines.push(e?.record_date ? `Record date: ${e.record_date}.` : "No record date announced.");
  if (e?.last_agm) lines.push(`Last annual meeting: ${e.last_agm}.`);
  const news = (company?.news ?? []).slice(0, 3);
  return (
    <Card title="Coming up and recent">
      {company ? (
        <>
          <ul className="plain small">{lines.map((l) => <li key={l}>{l}</li>)}</ul>
          {news.length ? (
            <ul className="plain small">{news.map((n) => <li key={`${n.day}-${n.title}`}><span className="mute">{n.day}</span> {n.title}</li>)}</ul>
          ) : (
            <p className="small mute" style={{ marginBottom: 0 }}>No recent company news.</p>
          )}
        </>
      ) : (
        <p className="small mute" style={{ margin: 0 }}>Company data is loading or not available.</p>
      )}
    </Card>
  );
}
