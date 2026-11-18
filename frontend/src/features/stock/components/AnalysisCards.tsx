import { num, pct, tone } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { KeyValueTable } from "@/shared/ui/Stat";
import type { Analysis } from "../schemas/analysis";

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
          {[...l.above].reverse().map((x) => <tr key={`r${x}`}><th className="dn">R</th><td>{num(x)}</td></tr>)}
          <tr><th>Price</th><td><b>{num(l.price)}</b></td></tr>
          {l.below.map((x) => <tr key={`s${x}`}><th className="up">S</th><td>{num(x)}</td></tr>)}
          <tr><th>52w</th><td>{num(l.low_52w)} – {num(l.high_52w)}</td></tr>
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
  const i = analysis.indicators;
  const get = (k: string) => i[k] ?? null;
  return (
    <Card title="Indicators">
      <KeyValueTable
        rows={[
          ["RSI(14)", num(get("rsi14"), 1)],
          ["MACD / signal / hist", `${num(get("macd"))} / ${num(get("macd_signal"))} / ${num(get("macd_hist"))}`],
          ["EMA 9 / 21", `${num(get("ema9"))} / ${num(get("ema21"))}`],
          ["SMA 20 / 50 / 200", `${num(get("sma20"))} / ${num(get("sma50"))} / ${num(get("sma200"))}`],
          ["Bollinger (20,2)", `${num(get("bb_lower"))} – ${num(get("bb_upper"))}`],
          ["ATR(14)", num(get("atr14"))],
          ["Volume vs 20d avg", `${num(get("vol_ratio"))}×`],
        ]}
      />
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

export function SummaryCard({ analysis }: { analysis: Analysis }) {
  return (
    <Card title="Summary">
      <ul className="plain">{analysis.summary.map((s) => <li key={s}>{s}</li>)}</ul>
      <p className="small mute">{analysis.disclaimer}</p>
    </Card>
  );
}
