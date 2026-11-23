import { crore, int, num, pct, text, tone } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { KeyValueTable } from "@/shared/ui/Stat";
import type { Analysis } from "../schemas/analysis";
import type { Company } from "@/features/company";
import { dividendYield, fairValueReading } from "../utils/reading";
import type { PeContext } from "../utils/summary";
import { fitReading, scaleFor } from "../utils/valuation";

const FIT_MARK = { yes: "✓", partly: "~", no: "✗" } as const;
const FIT_CLASS = { yes: "up", partly: "warn", no: "mute" } as const;
const FIT_WORD = { yes: "Fits this share", partly: "Fits partly", no: "Does not fit this share" } as const;

/** Fair value from several methods, each marked for whether it suits this share, on one shared scale beside the price. */
export function ValuationCard({ analysis, company }: { analysis: Analysis; company: Company | undefined }) {
  const v = analysis.valuation;
  const all = fairValueReading(analysis);
  const fit = fitReading(analysis, company);
  const price = analysis.price.ltp;
  const at = scaleFor(v.rows.map((r) => r.fair_value).filter((x): x is number => x != null && x > 0), price);
  const fitOf = (method: string) => fit?.fits.find((f) => f.method === method);
  return (
    <Card title="Fair value">
      {fit ? (
        <p data-field="fair_value_summary" style={{ marginTop: 0 }}>
          <b className={tone(fit.gapPct)}>{fit.text.split(". ")[0]}.</b> {fit.text.split(". ").slice(1).join(". ")}
        </p>
      ) : all ? (
        <p data-field="fair_value_summary" style={{ marginTop: 0 }}>
          <b className={tone(all.gapPct)}>{all.text.split(". ")[0]}.</b> {all.text.split(". ").slice(1).join(". ")}
        </p>
      ) : null}
      {fit && all ? <p className="small mute">Using all {all.total} methods instead, the median is {num(all.median)} ({pct(all.gapPct, 0)}). The {fit.excluded.length} left out are marked below with the reason.</p> : null}
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr><th>Method</th><th>Fits?</th><th className="r">Fair</th><th className="r">vs price</th><th className="hide-sm" aria-label="Position against the price" style={{ minWidth: 150 }}>Against the price (line)</th></tr>
          </thead>
          <tbody>
            {v.rows.map((r) => {
              const f = fitOf(r.method);
              const cls = f ? f.fit : "yes";
              return (
                <tr key={r.method} className={cls === "no" ? "mute" : undefined}>
                  <td>
                    {r.method}
                    <div className="small mute">{r.inputs}</div>
                    {f && f.fit !== "yes" ? <div className="small">{f.why}</div> : null}
                  </td>
                  <td className={FIT_CLASS[cls]} title={FIT_WORD[cls]}><span aria-hidden="true">{FIT_MARK[cls]}</span><span className="sr-only">{FIT_WORD[cls]}</span></td>
                  <td className="r num">{num(r.fair_value)}</td>
                  <td className={`r num ${tone(r.gap_pct)}`}>{pct(r.gap_pct, 0)}</td>
                  <td className="hide-sm">
                    <span className="vtrack" aria-hidden="true">
                      {price != null ? <i className="vprice" style={{ left: `${at(price)}%` }} /> : null}
                      {r.fair_value != null ? <i className={`vdot ${cls}`} style={{ left: `${at(r.fair_value)}%` }} /> : null}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <ul className="small mute">{v.notes.map((n) => <li key={n}>{n}</li>)}</ul>
    </Card>
  );
}

/** How the share's price compares with the market and its sector, in plain words. */
export function MarketComparisonCard({ analysis, pe }: { analysis: Analysis; pe: PeContext | null }) {
  const f = analysis.fundamentals;
  const sector = pe?.sector;
  const rows: Array<[string, string]> = [
    ["This share's P/E", f.pe == null ? "–" : num(f.pe, 1)],
    ["Market median P/E", pe?.marketMedian == null ? "–" : num(pe.marketMedian, 1)],
    ["Market P/E, size-weighted", pe?.marketWeighted == null ? "–" : num(pe.marketWeighted, 1)],
    [sector ? `${sector.name} median P/E (${sector.companies} companies)` : "Sector median P/E", sector?.median == null ? "–" : num(sector.median, 1)],
  ];
  const small = sector != null && sector.companies < 5;
  return (
    <Card title="Against the market">
      <KeyValueTable rows={rows.filter(([, v]) => v !== "–")} />
      <ul className="small mute">
        <li>P/E is the price divided by a year of earnings per share: how many years of profit you pay for.</li>
        <li>The market median is pulled up by many small, weak companies. The size-weighted figure counts big companies for more, so a big share is better judged against it.</li>
        {small ? <li>{sector.name} has only {sector.companies} companies here, too few to call a norm, so the market figures are used for the rating.</li> : null}
      </ul>
    </Card>
  );
}

export function FundamentalsCard({ analysis }: { analysis: Analysis }) {
  const f = analysis.fundamentals;
  const sh = f.shareholding;
  const dy = dividendYield(analysis);
  const empty = (v: string) => /^[–\-/\s]*$/.test(v); // "–", "– / – / –": nothing to show
  const rows: Array<[string, string]> = [
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
          ["Dividend yield", dy.value == null ? "–" : `${num(dy.value, 1)}% (${dy.basis})`],
          ["52w range", `${text(f.week_low_52)} – ${text(f.week_high_52)}`],
  ];
  return (
    <Card title="Fundamentals">
      <KeyValueTable rows={rows.filter(([, v]) => !empty(v))} />
    </Card>
  );
}
