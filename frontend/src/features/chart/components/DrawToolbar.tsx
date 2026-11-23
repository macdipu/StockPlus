"use client";

import { COLORS, TOOLS, WIDTHS, type Drawing, type Tool } from "../utils/drawings";

interface Props {
  tool: Tool;
  onTool: (t: Tool) => void;
  magnet: boolean;
  onMagnet: (on: boolean) => void;
  count: number;
  canDelete: boolean;
  onUndo: () => void;
  onClear: () => void;
  /** The drawing selected on the chart, if any: its colour and thickness can be changed. */
  selected: Drawing | null;
  onStyle: (patch: { color?: string; width?: number }) => void;
  onDeleteSelected: () => void;
}

/** Choose what a click on the chart does. "Select" is the normal mode; the rest place a drawing. */
export function DrawToolbar({ tool, onTool, magnet, onMagnet, count, canDelete, onUndo, onClear, selected, onStyle, onDeleteSelected }: Props) {
  const hint = TOOLS.find((t) => t.key === tool)?.hint ?? "";
  return (
    <div className="drawbar" role="toolbar" aria-label="Drawing tools">
      <div className="seg" role="group" aria-label="Tool">
        {TOOLS.map((t) => (
          <button key={t.key} type="button" aria-pressed={tool === t.key} title={t.hint} className={tool === t.key ? "on" : ""} onClick={() => onTool(t.key)}>
            {t.label}
          </button>
        ))}
      </div>
      <label className="layer-opt small" title="Snap clicks to the candle's open, high, low or close">
        <input type="checkbox" checked={magnet} onChange={(e) => onMagnet(e.target.checked)} /> Snap to candle
      </label>
      <button type="button" className="btn ghost small" disabled={count === 0} onClick={onUndo}>Undo</button>
      <button type="button" className="btn ghost small" disabled={!canDelete} onClick={onClear}>Clear all{count ? ` (${count})` : ""}</button>
      <div className="drawstyle" role="group" aria-label="Drawing style">
        {selected ? (
          <>
            <span className="small mute">Selected:</span>
            {COLORS.map((c) => (
              <button
                key={c.value}
                type="button"
                className={`swatchbtn${(selected.color ?? COLORS[0]?.value) === c.value ? " on" : ""}`}
                style={{ background: c.value }}
                aria-label={`${c.name} line`}
                aria-pressed={(selected.color ?? COLORS[0]?.value) === c.value}
                onClick={() => onStyle({ color: c.value })}
              />
            ))}
            <div className="seg" role="group" aria-label="Line thickness">
              {WIDTHS.map((w) => (
                <button key={w} type="button" aria-pressed={(selected.width ?? 2) === w} className={(selected.width ?? 2) === w ? "on" : ""} onClick={() => onStyle({ width: w })}>
                  {w}px
                </button>
              ))}
            </div>
            <button type="button" className="btn ghost small" onClick={onDeleteSelected}>Delete</button>
          </>
        ) : (
          <span className="small mute" role="status">
            {tool === "cursor" ? "Click a drawing to change its colour or thickness, or drag it to move it." : `${hint}. Esc cancels.`}
          </span>
        )}
      </div>
    </div>
  );
}
