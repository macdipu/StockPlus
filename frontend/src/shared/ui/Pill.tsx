/** Signal colours live in globals.css (`--sig-*`), so dark mode gets its own contrast-checked shades. */
const COLORS: Record<string, string> = {
  "STRONG BUY": "var(--sig-strong-buy)",
  BUY: "var(--sig-buy)",
  HOLD: "var(--sig-hold)",
  SELL: "var(--sig-sell)",
  "STRONG SELL": "var(--sig-strong-sell)",
  AVOID: "var(--sig-avoid)",
};

export function SignalPill({ action }: { action: string }) {
  return (
    <span className="pill" style={{ background: COLORS[action] ?? "var(--sig-hold)" }} data-testid="signal">
      {action}
    </span>
  );
}
