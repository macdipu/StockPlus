import { crore, int, num, pct, text, tone } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { KeyValueTable } from "@/shared/ui/Stat";
import type { Analysis } from "../schemas/analysis";

export function ValuationCard({ analysis }: { analysis: Analysis }) {
  const v = analysis.valuation;
  return (
    <Card title="Fair value">
      <table>
        <thead>
          <tr><th>Method</th><th>Inputs</th><th className="r">Fair</th><th className="r">vs price</th></tr>
        </thead>
        <tbody>
          {v.rows.map((r) => (
            <tr key={r.method}>
              <td>{r.method}</td>
              <td className="small mute">{r.inputs}</td>
              <td className="r">{num(r.fair_value)}</td>
              <td className={`r ${tone(r.gap_pct)}`}>{pct(r.gap_pct, 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <ul className="small mute">{v.notes.map((n) => <li key={n}>{n}</li>)}</ul>
    </Card>
  );
}

export function FundamentalsCard({ analysis }: { analysis: Analysis }) {
  const f = analysis.fundamentals;
  const sh = f.shareholding;
  return (
    <Card title="Fundamentals">
      <KeyValueTable
        rows={[
          ["EPS TTM", text(f.eps_ttm)],
          ["EPS basis", text(f.eps_ttm_basis)],
          ["EPS Q1 / Q2 / Q3", [f.eps_q1, f.eps_q2, f.eps_q3].map(text).join(" / ")],
          ["NAV / share", text(f.nav)],
          ["P/E (TTM)", num(f.pe, 1)],
          ["P/E (DSE trailing)", num(f.pe_dse_trailing, 1)],
          ["Market cap", crore(f.market_cap)],
          ["Total shares", int(f.total_shares)],
          ["Sponsor %", text(sh.sponsor_pct)],
          ["Institute / Foreign / Public %", [sh.institution_pct, sh.foreign_pct, sh.public_pct].map(text).join(" / ")],
          ["Free float %", num(f.free_float_pct, 1)],
          ["Last dividend", f.last_dividend ? `${f.last_dividend.cash_pct}% cash, ${f.last_dividend.stock_pct}% stock (${f.last_dividend.year})` : "–"],
          ["Dividend yield %", text(f.dividend_yield_pct)],
          ["52w range", `${text(f.week_low_52)} – ${text(f.week_high_52)}`],
        ]}
      />
    </Card>
  );
}
