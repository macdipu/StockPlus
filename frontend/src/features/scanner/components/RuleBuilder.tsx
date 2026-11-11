"use client";

import { Card } from "@/shared/ui/Card";
import type { Fields } from "../schemas/scanner";
import { newRule, NO_OPERAND_OPS, type DraftRule } from "../utils/rules";

interface Props {
  fields: Fields;
  rules: readonly DraftRule[];
  match: "all" | "any";
  problem: string | null;
  onRules: (rules: DraftRule[]) => void;
  onMatch: (m: "all" | "any") => void;
  onRun: () => void;
  running: boolean;
}

export function RuleBuilder({ fields, rules, match, problem, onRules, onMatch, onRun, running }: Props) {
  const names = Object.keys(fields.fields).sort();
  const patch = (i: number, p: Partial<DraftRule>) => onRules(rules.map((r, j) => (j === i ? { ...r, ...p } : r)));
  const option = (f: string) => (
    <option key={f} value={f}>{f} — {fields.fields[f]}</option>
  );
  return (
    <Card title="Custom scanner">
      {rules.map((r, i) => {
        const noOperand = NO_OPERAND_OPS.has(r.op);
        return (
          <div className="rule" key={i} role="group" aria-label={`Rule ${i + 1}`}>
            <select className="sel" aria-label="Field" value={r.field} onChange={(e) => patch(i, { field: e.target.value })}>
              {!names.includes(r.field) ? <option value={r.field}>{r.field}</option> : null}
              {names.map(option)}
            </select>
            <select className="sel" aria-label="Operator" value={r.op} onChange={(e) => patch(i, { op: e.target.value })}>
              {fields.ops.map((o) => <option key={o}>{o}</option>)}
            </select>
            <select className="sel" aria-label="Compare with field" value={r.field2} disabled={noOperand} onChange={(e) => patch(i, { field2: e.target.value })}>
              <option value="">(value)</option>
              {names.map(option)}
            </select>
            <input
              className="inp"
              aria-label="Value"
              style={{ width: 170 }}
              disabled={noOperand || r.field2 !== ""}
              placeholder="value, or a,b for between / in"
              value={r.value}
              onChange={(e) => patch(i, { value: e.target.value })}
            />
            <button className="btn ghost" type="button" aria-label={`Remove rule ${i + 1}`} disabled={rules.length === 1} onClick={() => onRules(rules.filter((_, j) => j !== i))}>×</button>
          </div>
        );
      })}
      <div className="rule">
        <button className="btn ghost" type="button" onClick={() => onRules([...rules, newRule()])} disabled={rules.length >= 20}>+ rule</button>
        <select className="sel" aria-label="Match mode" value={match} onChange={(e) => onMatch(e.target.value === "any" ? "any" : "all")}>
          <option value="all">match ALL</option>
          <option value="any">match ANY</option>
        </select>
        <button className="btn" type="button" onClick={onRun} disabled={running}>Run custom scan</button>
      </div>
      {problem ? <div className="notice error" role="alert">{problem}</div> : null}
    </Card>
  );
}
