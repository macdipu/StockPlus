const COLORS: Record<string, string> = {
  "STRONG BUY": "#15803d",
  BUY: "#16a34a",
  HOLD: "#64748b",
  SELL: "#dc2626",
  "STRONG SELL": "#991b1b",
  AVOID: "#0f172a",
};

export function SignalPill({ action }: { action: string }) {
  return (
    <span className="pill" style={{ background: COLORS[action] ?? "#64748b" }} data-testid="signal">
      {action}
    </span>
  );
}
