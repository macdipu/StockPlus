import { num, pct, pctPlain, tone } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { SignalPill } from "@/shared/ui/Pill";
import { Stat } from "@/shared/ui/Stat";
import type { Analysis } from "../schemas/analysis";
import { actionSentence, edgeReading } from "../utils/reading";

const rate = (v: number | null | undefined) => (v == null ? "–" : pctPlain(v * 100, 0));

export function SignalCard({ analysis }: { analysis: Analysis }) {
  const { signal, setup, probability: p } = analysis;
  const sim = p.similar_setups;
  const edge = edgeReading(sim.p_target_first, p.all_days_baseline.p_target_first, sim.n, p.reliable);
  return (
    <Card label="Signal">
      <div className="hero" style={{ alignItems: "center" }}>
        <SignalPill action={signal.action} />
        <div style={{ flex: 1, minWidth: 220 }}>
          <p style={{ margin: "0 0 4px" }}><b>{actionSentence(signal.action)}.</b></p>
          <p className={`small ${edge.tone}`} style={{ margin: 0 }}>{edge.text}</p>
        </div>
      </div>
      <div className="kv" style={{ marginTop: 10 }}>
        <Stat label="Setup score (of 6 checks passed)">{setup.score} / {setup.max}</Stat>
        <Stat label="Reward for each unit of risk" tone={setup.plan.rr_ok ? "up" : "dn"}>{num(setup.plan.rr)}</Stat>
        <Stat label="Similar setups hit target first">{rate(sim.p_target_first)}</Stat>
        <Stat label="An ordinary day hits target first">{rate(p.all_days_baseline.p_target_first)}</Stat>
        <Stat label="Average result per trade" tone={tone(sim.expectancy_pct)}>{pct(sim.expectancy_pct, 2)}</Stat>
        <Stat label="Past cases it is based on">{sim.n}</Stat>
      </div>
      <p className={`small ${p.warning ? "dn" : "mute"}`}>
        {p.warning ??
          `Target +${num(p.target_pct, 1)}% before stop −${num(p.stop_pct, 1)}% within ${p.horizon_sessions} sessions. Historical frequency, not a forecast.`}
      </p>
      <div className="grid2 small">
        <div>
          <b className="up">Bullish</b>
          <ul className="plain">
            {signal.bullish_reasons.length ? signal.bullish_reasons.map((r) => <li key={r}>{r}</li>) : <li className="mute">none</li>}
          </ul>
        </div>
        <div>
          <b className="dn">Bearish</b>
          <ul className="plain">
            {signal.bearish_reasons.length ? signal.bearish_reasons.map((r) => <li key={r}>{r}</li>) : <li className="mute">none</li>}
          </ul>
        </div>
      </div>
    </Card>
  );
}
