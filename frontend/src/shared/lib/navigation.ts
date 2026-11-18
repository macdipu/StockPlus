/**
 * The site map: every top-level section and the views inside it, in one place. Navigation, page headers and
 * in-app links all read from here, so a route or a label changes once.
 *
 * `plan` marks which subscription tier a view belongs to. Everything is "free" today and nothing is gated;
 * when a paid tier launches, moving a view to "pro" (plus a paywall check where the view renders) is the whole
 * change: no restructuring of routes or menus.
 */

export type Plan = "free" | "pro";

export const routes = {
  market: "/",
  find: "/find",
  findRules: (preset?: string | null) => (preset ? `/find/rules/${encodeURIComponent(preset)}` : "/find/rules"),
  findTable: (sector?: string | null) => (sector ? `/find/table?sector=${encodeURIComponent(sector)}` : "/find/table"),
  stock: (symbol?: string | null) => (symbol ? `/stock/${encodeURIComponent(symbol)}` : "/stock"),
  tools: "/tools",
} as const;

export interface View {
  key: string;
  href: string;
  label: string;
  description: string;
  plan: Plan;
}

export interface Section {
  key: "market" | "find" | "stock" | "tools";
  label: string;
  href: string;
  description: string;
  /** Path prefixes that belong to this section (for the active tab). */
  paths: readonly string[];
  views: readonly View[];
}

export const SECTIONS: readonly Section[] = [
  {
    key: "market",
    label: "Market",
    href: routes.market,
    description: "How the market is doing today: sectors, top movers, P/E, 52-week highs and lows.",
    paths: ["/market"],
    views: [],
  },
  {
    key: "find",
    label: "Find shares",
    href: routes.find,
    description: "Shares ranked for you, shares that match your own rules, or every share in one table.",
    paths: ["/find"],
    views: [
      {
        key: "picks",
        href: routes.find,
        label: "Picks",
        description: "Every share scored for value for money and entry timing, then ranked. Start here.",
        plan: "free",
      },
      {
        key: "rules",
        href: routes.findRules(),
        label: "Custom rules",
        description: "Ready-made scans or your own rules: shares that match, nothing more.",
        plan: "free",
      },
      {
        key: "table",
        href: routes.findTable(),
        label: "All shares table",
        description: "Every share's fundamentals or technical values in one sortable table, with CSV export.",
        plan: "free",
      },
    ],
  },
  {
    key: "stock",
    label: "Stock",
    href: routes.stock(),
    description: "One share in depth: chart, candle analysis, trade plan and company details.",
    paths: ["/stock"],
    views: [],
  },
  {
    key: "tools",
    label: "Tools",
    href: routes.tools,
    description: "Profit after fees, correlation between shares, price history download.",
    paths: ["/tools"],
    views: [],
  },
];

export function sectionFor(pathname: string): Section | undefined {
  if (pathname === "/") return SECTIONS[0];
  return SECTIONS.find((s) => s.paths.some((p) => pathname === p || pathname.startsWith(`${p}/`)));
}

/** The view a path belongs to: the longest matching view href wins ("/find/rules/x" → Custom rules). */
export function viewFor(section: Section, pathname: string): View | undefined {
  return [...section.views]
    .sort((a, b) => b.href.length - a.href.length)
    .find((v) => pathname === v.href || pathname.startsWith(`${v.href}/`));
}
