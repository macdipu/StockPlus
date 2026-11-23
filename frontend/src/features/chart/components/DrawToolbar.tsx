"use client";

import { TOOLS, type Tool } from "../utils/drawings";

interface Props {
  tool: Tool;
  onTool: (t: Tool) => void;
  magnet: boolean;
  onMagnet: (on: boolean) => void;
  count: number;
  canDelete: boolean;
  onUndo: () => void;
  onClear: () => void;
}

/** Choose what a click on the chart does. "Select" is the normal mode; the rest place a drawing. */
export function DrawToolbar({ tool, onTool, magnet, onMagnet, count, canDelete, onUndo, onClear }: Props) {
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
      {tool !== "cursor" ? <span className="small mute" role="status">{hint}. Esc cancels.</span> : null}
    </div>
  );
}
