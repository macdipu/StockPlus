import Link from "next/link";
import { routes } from "@/shared/lib/navigation";
import { Card } from "@/shared/ui/Card";
import type { Preset } from "../schemas/scanner";

export function PresetPicker({ presets, active }: { presets: readonly Preset[]; active: string | null }) {
  const groups = new Map<string, Preset[]>();
  for (const p of presets) groups.set(p.group, [...(groups.get(p.group) ?? []), p]);
  return (
    <Card title="Preset scanners">
      {[...groups].map(([group, items]) => (
        <div key={group} style={{ marginBottom: 8 }}>
          <div className="small mute" id={`group-${group}`}>{group}</div>
          <div className="chips" role="group" aria-labelledby={`group-${group}`}>
            {items.map((p) => (
              <Link
                key={p.key}
                href={routes.findRules(p.key)}
                className={`chip ${p.key === active ? "on" : ""}`}
                aria-current={p.key === active ? "true" : undefined}
                title={p.description}
                style={{ textDecoration: "none" }}
              >
                {p.name}
                {p.premarket ? " ☾" : ""}
              </Link>
            ))}
          </div>
        </div>
      ))}
      <p className="small mute" style={{ marginBottom: 0 }}>☾ = pre-market scan: evaluates the last completed session by default.</p>
    </Card>
  );
}
