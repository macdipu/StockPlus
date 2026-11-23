import { num } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import type { Analysis } from "../schemas/analysis";
import { withoutRepeatedWatch } from "../utils/reading";

const BIAS = { bullish: "up", bearish: "dn", neutral: "mute" } as const;
const KIND = { entry: "Buy zone", stop: "Exit below (stop)", target: "Take profit", watch: "Watch" } as const;
const TONE = { entry: "", stop: "dn", target: "up", watch: "" } as const;

/**
 * The one trade plan on the page: levels (buy zone from nearby support, stop, targets, watch levels), the same
 * plan in words, and what the last five candles say. The same levels are drawn on the chart at Analysis: Full.
 */
export function TradePlanCard({ analysis }: { analysis: Analysis }) {
  const st = analysis.candle_story;
  const { plan, flags } = analysis.setup;
  if (!st) return null;
  return (
    <Card title="Trade plan">
      <div data-agent="candle-analysis">
        <p className={`where ${st.where}`}><b>{st.headline}</b></p>
        <div className="grid2">
          <div>
            <table data-agent="levels">
              <tbody>
                {withoutRepeatedWatch(st.annotations).map((a) => (
                  <tr key={`${a.kind}-${a.price}`} data-field={a.kind}>
                    <th scope="row">{a.kind === "target" && a.label.startsWith("TARGET 2") ? "Second target" : KIND[a.kind]}</th>
                    <td className={`r num ${TONE[a.kind]}`}>{a.price_to != null ? `${num(a.price_to)} – ${num(a.price)}` : num(a.price)}</td>
                  </tr>
                ))}
                <tr><th scope="row">ATR (typical daily move)</th><td className="r num">{num(plan.atr)}</td></tr>
              </tbody>
            </table>
            {flags.length ? <div className="small dn" style={{ marginTop: 6 }}>{flags.map((f) => <div key={f}>⚠ {f}</div>)}</div> : null}
            <dl className="plan" style={{ marginTop: 12 }}>
              {st.plan.map((p) => (
                <div key={p.step} data-field={p.step}>
                  <dt>{p.step}</dt>
                  <dd>{p.text}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div>
            <h4 className="small mute" style={{ margin: "0 0 6px" }}>What the last candles say (newest last)</h4>
            <ol className="candles plain">
              {st.recent.map((c) => (
                <li key={c.date} className={BIAS[c.bias]}>
                  <span className="small num" style={{ display: "inline-block", minWidth: 84 }}>{c.date}</span>
                  <i className={`cndl ${c.colour}`} aria-hidden="true" />
                  <span className="ink">{c.text}</span>
                  {c.vol_ratio != null ? <span className="small mute"> · vol {num(c.vol_ratio, 1)}×</span> : null}
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>
    </Card>
  );
}
