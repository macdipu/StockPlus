import { num, pct, pctPlain, tone } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { SignalPill } from "@/shared/ui/Pill";
import { Stat } from "@/shared/ui/Stat";
import type { Analysis } from "../schemas/analysis";

const rate = (v: number | null | undefined) => (v == null ? "–" : pctPlain(v * 100, 0));

export function SignalCard({ analysis }: { analysis: Analysis }) {
  const { signal, setup, probability: p } = analysis;
  const sim = p.similar_setups;
  return (
    <Card label="Signal">
      <div className="hero" style={{ alignItems: "center" }}>
        <SignalPill action={signal.action} />
        <div className="kv" style={{ flex: 1 }}>
          <Stat label="Setup score">{setup.score} / {setup.max}</Stat>
          <Stat label="Risk / reward (if bought now)" tone={setup.plan.rr_ok ? "up" : "dn"}>{num(setup.plan.rr)}</Stat>
          <Stat label="Hit rate (similar)">{rate(sim.p_target_first)}</Stat>
          <Stat label="Baseline (all days)">{rate(p.all_days_baseline.p_target_first)}</Stat>
          <Stat label="Expectancy / trade" tone={tone(sim.expectancy_pct)}>{pct(sim.expectancy_pct, 2)}</Stat>
          <Stat label="Samples">{sim.n}</Stat>
        </div>
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
