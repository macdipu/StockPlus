"use client";

import { useMemo, useState } from "react";
import { Card } from "@/shared/ui/Card";
import { ErrorNotice, Loading } from "@/shared/ui/Notice";
import { useCustomScan, useFields, usePresetScan, usePresets } from "../hooks/use-scanner-queries";
import type { SavedScan } from "../schemas/scanner";
import { buildScanBody, defaultRules, draftFromDefinition, ruleProblem, type DraftFilters, type DraftRule } from "../utils/rules";
import { PresetPicker } from "./PresetPicker";
import { RuleBuilder } from "./RuleBuilder";
import { SavedScansCard } from "./SavedScansCard";
import { ScanResults } from "./ScanResults";

const DEFAULT_PRESET = "short_term_setup";
const NO_FILTERS: DraftFilters = { category: "", minValueMn: "", live: "" };

export function ScannerPage({ presetKey }: { presetKey: string | null }) {
  const presets = usePresets();
  const fields = useFields();
  const key = presetKey ?? DEFAULT_PRESET;

  const [filters, setFilters] = useState<DraftFilters>(NO_FILTERS);
  const [rules, setRules] = useState<DraftRule[]>(defaultRules);
  const [match, setMatch] = useState<"all" | "any">("all");
  // `custom` = the user ran the rule builder. Picking a preset (the URL changes) switches back.
  const [custom, setCustom] = useState<{ rules: DraftRule[]; match: "all" | "any"; fromKey: string | null } | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const customActive = custom !== null && custom.fromKey === presetKey;
  const preset = presets.data?.find((p) => p.key === key);
  const presetScan = usePresetScan(key, filters, !customActive);
  const body = useMemo(() => (customActive && custom ? buildScanBody(custom.rules, custom.match, filters) : null), [customActive, custom, filters]);
  const customScan = useCustomScan(body);

  const firstProblem = rules.map(ruleProblem).find((p) => p !== null) ?? null;
  const run = () => {
    setProblem(firstProblem);
    if (!firstProblem) setCustom({ rules, match, fromKey: presetKey });
  };
  const load = (s: SavedScan) => {
    const d = draftFromDefinition(s.definition);
    setRules(d.rules);
    setMatch(d.match);
    setFilters(d.filters);
    setProblem(null);
    setCustom({ rules: d.rules, match: d.match, fromKey: presetKey });
  };

  if (presets.isPending || fields.isPending) return <Card label="Loading"><Loading what="Loading scanners" /></Card>;
  if (presets.isError || fields.isError) return <Card label="Error"><ErrorNotice error={presets.error ?? fields.error} onRetry={() => { void presets.refetch(); void fields.refetch(); }} /></Card>;

  const set = <K extends keyof DraftFilters>(k: K, v: DraftFilters[K]) => setFilters((f) => ({ ...f, [k]: v }));
  return (
    <>
      <PresetPicker presets={presets.data} active={customActive ? null : key} />
      <RuleBuilder fields={fields.data} rules={rules} match={match} problem={problem} onRules={setRules} onMatch={setMatch} onRun={run} running={customScan.isFetching} />
      <Card title="Filters">
        <div className="row">
          <select className="sel" aria-label="Category" value={filters.category} onChange={(e) => set("category", e.target.value)}>
            <option value="">All categories</option>
            {["A", "B", "N", "Z"].map((c) => <option key={c}>{c}</option>)}
          </select>
          <input className="inp" aria-label="Minimum turnover (BDT mn)" type="number" min="0" step="0.5" placeholder="Min turnover mn" style={{ width: 150 }} value={filters.minValueMn} onChange={(e) => set("minValueMn", e.target.value)} />
          <select className="sel" aria-label="Session" value={filters.live} onChange={(e) => set("live", e.target.value as DraftFilters["live"])}>
            <option value="">Session: scan default</option>
            <option value="true">Live (today)</option>
            <option value="false">Last close (pre-market)</option>
          </select>
        </div>
      </Card>
      <SavedScansCard current={firstProblem ? { problem: firstProblem } : { body: buildScanBody(rules, match, filters) }} onLoad={load} />
      {customActive ? (
        <ScanResults title="Custom scan" description={body ? JSON.stringify(body.rules) : undefined} query={customScan} fields={fields.data} />
      ) : (
        <ScanResults title={preset?.name ?? key} description={preset?.description} query={presetScan} fields={fields.data} />
      )}
    </>
  );
}
