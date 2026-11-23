/** Chart sizes. The price pane keeps its height; each indicator panel (RSI, MACD...) adds its own, or only a thin strip
 * when collapsed, so hiding one hands the space to the candles. */
export const BASE_HEIGHT = 440;
export const PANE_HEIGHT = 120; // outer: includes the gap between panels
export const COLLAPSED_PANE_HEIGHT = 26;
export const SUBPANE_HEIGHT = 110; // inner: the drawing area the library is told to use
export const COLLAPSED_SUBPANE_HEIGHT = 22;

export function chartHeight(panes: number, collapsed: number): number {
  const shut = Math.min(Math.max(collapsed, 0), panes);
  return BASE_HEIGHT + PANE_HEIGHT * (panes - shut) + COLLAPSED_PANE_HEIGHT * shut;
}

export const paneHeight = (collapsed: boolean): number => (collapsed ? COLLAPSED_SUBPANE_HEIGHT : SUBPANE_HEIGHT);
