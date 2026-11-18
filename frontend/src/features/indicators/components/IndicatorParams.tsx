"use client";

import { useState } from "react";
import type { CatalogEntry } from "../schemas/catalog";
import { clampValues, formatSpec, specValues } from "../utils/spec";

interface Props {
  entry: CatalogEntry;
  spec: string;
  onApply: (spec: string) => void;
  onCancel: () => void;
}

/** Edit an indicator's parameters. Values outside the allowed range are pulled back into it on Apply. */
export function IndicatorParams({ entry, spec, onApply, onCancel }: Props) {
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(Object.entries(specValues(entry, spec)).map(([k, v]) => [k, String(v)])),
  );
  if (entry.params.length === 0) return <p className="small mute" style={{ margin: 0 }}>{entry.name} has no settings.</p>;
  const apply = () => onApply(formatSpec(entry, clampValues(entry, Object.fromEntries(Object.entries(values).map(([k, v]) => [k, Number(v)])))));
  return (
    <form
      className="ind-params"
      aria-label={`${entry.name} settings`}
      onSubmit={(e) => {
        e.preventDefault();
        apply();
      }}
    >
      {entry.params.map((p) => (
        <label key={p.key} className="field">
          <span>{p.label}</span>
          <input
            className="inp"
            inputMode="decimal"
            value={values[p.key] ?? ""}
            onChange={(e) => setValues((v) => ({ ...v, [p.key]: e.target.value }))}
            aria-label={`${entry.name} ${p.label}`}
          />
          <span className="small mute">{p.min} to {p.max}</span>
        </label>
      ))}
      <div className="row" style={{ margin: 0 }}>
        <button className="btn small" type="submit">Apply</button>
        <button className="btn ghost small" type="button" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}
