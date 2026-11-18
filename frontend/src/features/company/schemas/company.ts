import { z } from "zod";

const n = z.number().nullable();
const s = z.string().nullable();

export const companySchema = z.object({
  symbol: z.string(),
  fetched_at: z.string(),
  price: n,
  profile: z.object({
    contact: z.object({ address: s, registered_office: s.optional(), factory_address: s.optional(), secretary: s.optional(), phone: s, fax: s, email: s, website: s }),
    listing_year: n,
    year_end: s,
    operational_status: s,
    credit_rating: z.object({ agency: s, long_term: s, short_term: s, outlook: s, rated_on: s }).nullable(),
  }),
  capital: z.object({
    authorized_mn: n,
    paid_up_mn: n,
    reserve_mn: n,
    long_term_loan_mn: n,
    short_term_loan_mn: n,
    total_loan_mn: n,
    total_shares: n,
    loans_as_of: s,
  }),
  per_share_history: z.array(
    z.object({
      period_end: z.string(),
      eps: n.optional(),
      nav: n.optional(),
      nocfps: n.optional(),
      cash_dividend_pct: n.optional(),
      stock_dividend_pct: n.optional(),
    }),
  ),
  quarterly_eps: z.array(z.object({ period_end: z.string(), period: z.string(), label: z.string(), eps: z.number() })),
  dividends: z.array(
    z.object({ period_end: z.string(), year: z.number(), cash_pct: z.number(), stock_pct: z.number(), cash_per_share: z.number() }),
  ),
  shareholding: z.array(z.object({ as_of: z.string(), director: n, government: n, institute: n, foreign: n, public: n })),
  financial_years: z.array(
    z.object({
      year: z.number(),
      revenue: n,
      gross_profit: n,
      net_profit: n,
      operating_cf: n,
      investing_cf: n,
      total_assets: n,
      total_equity: n,
      total_debt: n,
      cash: n,
      interest_expense: n,
      eps: n,
      nav_per_share: n,
      nocfps: n,
      dividend_cash_pct: n,
    }),
  ),
  statements: z.array(
    z.object({
      kind: z.enum(["income", "balance_sheet", "cash_flow"]),
      years: z.array(z.string()),
      rows: z.array(z.object({ label: z.string(), values: z.array(n), total: z.boolean() })),
    }),
  ),
  director_trades: z.array(z.object({ day: s, holder: z.string(), side: z.string(), quantity: n, price: n })),
  events: z.object({
    record_date: s,
    last_agm: s,
    declaration_date: s,
    declared_dividend_pct: n,
    declared_dividend_type: s,
  }),
  news: z.array(z.object({ day: s, title: z.string(), body: z.string() })),
  sources: z.array(z.object({ name: z.string(), ok: z.boolean(), url: z.string(), error: s })),
  ratios: z.array(z.object({ key: z.string(), label: z.string(), value: n, unit: z.string(), basis: z.string() })),
  flags: z.array(z.object({ tone: z.enum(["good", "warn", "bad"]), text: z.string() })),
});
export type Company = z.infer<typeof companySchema>;

export const alertSchema = z.object({
  symbol: z.string(),
  kind: z.string(),
  severity: z.enum(["info", "action", "warning"]),
  key: z.string(),
  price: z.number(),
  message: z.string(),
});
export type StockAlert = z.infer<typeof alertSchema>;
