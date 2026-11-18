"use client";

import { Fragment, useEffect, useRef, useState } from "react";
import { STYLE_GROUPS, needsOhlc, styleLabel, type ChartStyle } from "../utils/styles";

/** A menu of chart styles, grouped (bars, lines, areas, others), with a one-line hint for each. */
export function StylePicker({ value, onChange, closesOnly = false }: { value: ChartStyle; onChange: (s: ChartStyle) => void; closesOnly?: boolean }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => box.current && !box.current.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);
  return (
    <div className="stylepicker" ref={box}>
      <button type="button" className="btn ghost small" aria-haspopup="menu" aria-expanded={open} aria-label="Chart style" onClick={() => setOpen((o) => !o)}>
        {styleLabel(value)} <span aria-hidden="true">▾</span>
      </button>
      {open ? (
        <div className="menu" role="menu" aria-label="Chart styles">
          {STYLE_GROUPS.map((group, i) => (
            <Fragment key={i}>
              {i > 0 ? <hr /> : null}
              {group.map((s) => (
                <button
                  key={s.key}
                  type="button"
                  role="menuitemradio"
                  aria-checked={s.key === value}
                  disabled={closesOnly && needsOhlc(s.key)}
                  title={closesOnly && needsOhlc(s.key) ? "Needs open, high and low, which this series does not have" : s.hint}
                  className={s.key === value ? "on" : ""}
                  onClick={() => {
                    onChange(s.key);
                    setOpen(false);
                  }}
                >
                  {s.label}
                </button>
              ))}
            </Fragment>
          ))}
        </div>
      ) : null}
    </div>
  );
}
