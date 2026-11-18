"use client";

import type { KeyboardEvent } from "react";

interface TabBarProps<K extends string> {
  tabs: ReadonlyArray<{ key: K; label: string }>;
  value: K;
  onChange: (key: K) => void;
  label: string;
  idPrefix: string;
}

/** Accessible tab strip (WAI-ARIA tabs pattern): arrow keys move between tabs, Home/End jump to the ends. */
export function TabBar<K extends string>({ tabs, value, onChange, label, idPrefix }: TabBarProps<K>) {
  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const last = tabs.length - 1;
    const next =
      e.key === "ArrowRight" ? (index === last ? 0 : index + 1)
      : e.key === "ArrowLeft" ? (index === 0 ? last : index - 1)
      : e.key === "Home" ? 0
      : e.key === "End" ? last
      : null;
    const target = next === null ? undefined : tabs[next];
    if (!target) return;
    e.preventDefault();
    onChange(target.key);
    document.getElementById(`${idPrefix}-tab-${target.key}`)?.focus();
  };
  return (
    <div className="tabbar" role="tablist" aria-label={label}>
      {tabs.map((t, i) => (
        <button
          key={t.key}
          id={`${idPrefix}-tab-${t.key}`}
          type="button"
          role="tab"
          aria-selected={t.key === value}
          aria-controls={`${idPrefix}-panel-${t.key}`}
          tabIndex={t.key === value ? 0 : -1}
          onClick={() => onChange(t.key)}
          onKeyDown={(e) => onKeyDown(e, i)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
