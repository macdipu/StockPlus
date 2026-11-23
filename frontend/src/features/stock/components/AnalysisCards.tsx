import { num, pct, tone } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import type { Analysis } from "../schemas/analysis";
import { distance, indicatorRows, technicalReading } from "../utils/technicals";

export function ChecklistCard({ analysis }: { analysis: Analysis }) {
  return (
    <Card title="Setup checklist">
      <table>
        <tbody>
          {analysis.setup.checks.map((c) => (
            <tr key={c.key}>
              <td>{c.label}</td>
              <td className={c.pass ? "up" : "dn"} aria-label={c.pass ? "passed" : "failed"}>{c.pass ? "✔" : "✘"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export function LevelsCard({ analysis }: { analysis: Analysis }) {
  const l = analysis.levels;
  return (
    <Card title="Support / resistance">
      <table>
        <tbody>
          {[...l.above].reverse().map((x) => <tr key={`r${x}`}><th className="dn">Resistance</th><td>{num(x)} <span className="small mute">{distance(l.price, x)}</span></td></tr>)}
          <tr><th>Price</th><td><b>{num(l.price)}</b></td></tr>
          {l.below.map((x) => <tr key={`s${x}`}><th className="up">Support</th><td>{num(x)} <span className="small mute">{distance(l.price, x)}</span></td></tr>)}
          <tr><th>52-week range</th><td>{num(l.low_52w)} – {num(l.high_52w)}</td></tr>
        </tbody>
      </table>
    </Card>
  );
}

export function TrendCard({ analysis }: { analysis: Analysis }) {
  const { changes, vs_ma } = analysis.trend;
  return (
    <Card title="Trend">
      <table>
        <tbody>
          {Object.entries(changes).map(([k, v]) => <tr key={k}><th>{k}</th><td className={tone(v)}>{pct(v)}</td></tr>)}
          {Object.entries(vs_ma).map(([k, v]) => (
            <tr key={k}>
              <th>vs {k}</th>
              <td>{v ? <>{num(v.value)} <span className={tone(v.pct)}>({pct(v.pct)})</span></> : "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export function IndicatorsCard({ analysis }: { analysis: Analysis }) {
  const rows = indicatorRows(analysis);
  return (
    <Card title="Indicators">
      <div style={{ overflowX: "auto" }}>
        <table className="small">
          <thead><tr><th>Indicator</th><th className="r">Value</th><th>What it says</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label}>
                <th scope="row">{r.label}</th>
                <td className="r num">{r.value}</td>
                <td className={r.tone === "mute" ? "" : r.tone}>{r.reading}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/** The technical picture in plain words: a headline and one line each for trend, momentum, volume, swing and levels. */
export function TechnicalReadingCard({ analysis }: { analysis: Analysis }) {
  const r = technicalReading(analysis);
  if (!r) return null;
  return (
    <Card title="Technical reading">
      <p style={{ margin: "0 0 8px", fontSize: 16 }}><b>{r.headline}</b></p>
      <ul className="plain readinglines">
        {r.lines.map((l) => (
          <li key={l.topic}>
            <b className={l.tone === "mute" ? "" : l.tone}>{l.topic}.</b> {l.text}
          </li>
        ))}
      </ul>
      <p className="small mute" style={{ marginBottom: 0 }}>{analysis.disclaimer}</p>
    </Card>
  );
}

export function PatternsCard({ analysis }: { analysis: Analysis }) {
  const patterns = [...analysis.candles.patterns].reverse();
  return (
    <Card title="Candle patterns (last 10)">
      <p className="small">{analysis.candles.last_candle}</p>
      <table>
        <tbody>
          {patterns.length ? (
            patterns.map((p) => (
              <tr key={`${p.date}-${p.pattern}`}>
                <td>{p.date}</td>
                <td>{p.pattern}</td>
                <td className={p.direction === "bullish" ? "up" : p.direction === "bearish" ? "dn" : ""}>{p.direction}</td>
              </tr>
            ))
          ) : (
            <tr><td className="mute">None detected</td></tr>
          )}
        </tbody>
      </table>
    </Card>
  );
}
