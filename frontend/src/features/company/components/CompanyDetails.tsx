"use client";

import { useState } from "react";
import { DASH, int, num } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";
import { Chips } from "@/shared/ui/Chips";
import { ErrorNotice, Loading } from "@/shared/ui/Notice";
import { KeyValueTable } from "@/shared/ui/Stat";
import { useCompany } from "../hooks/use-company";
import type { Company } from "../schemas/company";

/** BDT → crore (1 crore = 10 million). Statements and yearly figures arrive in BDT. */
const cr = (v: number | null | undefined) => (v == null ? DASH : `${num(v / 1e7, 1)} cr`);
/** BDT million → crore. Capital and loans arrive in BDT million. */
const mnToCr = (v: number | null | undefined) => (v == null ? DASH : `${num(v / 10, 1)} cr`);
const yr = (iso: string) => iso.slice(0, 4);
const fmtDate = (iso: string | null | undefined) => {
  if (!iso) return DASH;
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
};
const TONE = { good: "up", warn: "", bad: "dn" } as const;
const ICON = { good: "✓", warn: "!", bad: "✕" } as const;

function Bars({ items, unit, label }: { items: ReadonlyArray<{ x: string; y: number | null | undefined }>; unit: string; label: string }) {
  const vals = items.map((i) => i.y ?? 0);
  const max = Math.max(...vals.map(Math.abs), 1e-9);
  const w = 34;
  const h = 90;
  return (
    <figure className="minibars" aria-label={label}>
      <svg viewBox={`0 0 ${items.length * w} ${h + 28}`} role="img" aria-label={label}>
        {items.map((it, i) => {
          const v = it.y ?? 0;
          const bh = (Math.abs(v) / max) * h;
          return (
            <g key={it.x}>
              <title>{`${it.x}: ${it.y == null ? "n/a" : `${num(v)} ${unit}`}`}</title>
              <rect x={i * w + 6} y={h - bh + 12} width={w - 12} height={Math.max(bh, 1)} rx={3} fill={v >= 0 ? "var(--up)" : "var(--dn)"} opacity={0.85} />
              <text x={i * w + w / 2} y={h - bh + 8} textAnchor="middle" fontSize="9" fill="var(--ink)">{it.y == null ? "" : num(v, Math.abs(v) >= 100 ? 0 : 1)}</text>
              <text x={i * w + w / 2} y={h + 24} textAnchor="middle" fontSize="9" fill="var(--mute)">{it.x}</text>
            </g>
          );
        })}
      </svg>
      <figcaption className="small mute">{label}</figcaption>
    </figure>
  );
}

function Overview({ c }: { c: Company }) {
  const p = c.profile;
  const r = p.credit_rating;
  const e = c.events;
  const ct = p.contact;
  return (
    <Card title="Company profile">
      <KeyValueTable
        rows={[
          ["Status", p.operational_status ?? DASH],
          ["Listed", p.listing_year ? String(p.listing_year) : DASH],
          ["Credit rating", r ? `${r.long_term ?? DASH} / ${r.short_term ?? DASH} · ${r.agency ?? ""} · ${r.outlook ?? ""} (${fmtDate(r.rated_on)})` : DASH],
          ["Last dividend declared", e.declared_dividend_pct != null ? `${e.declared_dividend_pct}% ${e.declared_dividend_type ?? ""} on ${fmtDate(e.declaration_date)}` : DASH],
          ["Record date", fmtDate(e.record_date)],
          ["Last AGM", fmtDate(e.last_agm)],
          ["Head office", ct.address ?? DASH],
          ...(ct.registered_office && ct.registered_office !== ct.address ? ([["Registered office", ct.registered_office]] as const) : []),
          ...(ct.factory_address ? ([["Factory", ct.factory_address]] as const) : []),
          ...(ct.secretary ? ([["Company secretary", ct.secretary]] as const) : []),
          ["Phone", ct.phone ?? DASH],
          ["Email", ct.email ?? DASH],
          ["Website", ct.website ? <a href={ct.website.startsWith("http") ? ct.website : `https://${ct.website}`} target="_blank" rel="noreferrer">{ct.website}</a> : DASH],
        ]}
      />
    </Card>
  );
}

function Health({ c }: { c: Company }) {
  return (
    <Card title="Financial health">
      <ul className="flags" data-agent="flags">
        {c.flags.map((f) => (
          <li key={f.text} className={TONE[f.tone]} data-tone={f.tone}>
            <b aria-hidden="true">{ICON[f.tone]}</b> {f.text}
          </li>
        ))}
        {c.flags.length === 0 ? <li className="mute">Not enough data for flags.</li> : null}
      </ul>
      <table className="small" data-agent="ratios">
        <tbody>
          {c.ratios.map((r) => (
            <tr key={r.key} data-field={r.key} title={r.basis}>
              <th scope="row">{r.label}</th>
              <td className="r num">{r.value == null ? DASH : `${num(r.value, r.unit === "x" ? 2 : 1)}${r.unit === "%" ? "%" : r.unit === "x" ? "×" : ""}`}</td>
              <td className="mute">{r.basis}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function Capital({ c }: { c: Company }) {
  const k = c.capital;
  return (
    <Card title="Capital and loans">
      <KeyValueTable
        rows={[
          ["Authorized capital", mnToCr(k.authorized_mn)],
          ["Paid-up capital", mnToCr(k.paid_up_mn)],
          ["Reserve & surplus", mnToCr(k.reserve_mn)],
          ["Total shares", int(k.total_shares)],
          ["Short-term loan", mnToCr(k.short_term_loan_mn)],
          ["Long-term loan", mnToCr(k.long_term_loan_mn)],
          ["Total loans", `${mnToCr(k.total_loan_mn)}${k.loans_as_of ? ` (as of ${fmtDate(k.loans_as_of)})` : ""}`],
        ]}
      />
    </Card>
  );
}

function PerShare({ c }: { c: Company }) {
  const rows = c.per_share_history.slice(0, 10);
  const chrono = [...rows].reverse();
  return (
    <Card title="EPS, NAV, cash flow and dividend by year">
      <div className="grid2" style={{ marginBottom: 10 }}>
        <Bars label="EPS (Tk per share)" unit="Tk" items={chrono.map((r) => ({ x: yr(r.period_end), y: r.eps }))} />
        <Bars label="Cash dividend (% of face value)" unit="%" items={chrono.map((r) => ({ x: yr(r.period_end), y: r.cash_dividend_pct }))} />
      </div>
      <div className="tablewrap">
        <table className="num">
          <thead>
            <tr><th>Year end</th><th className="r">EPS</th><th className="r">NAV</th><th className="r">NOCF/share</th><th className="r">Cash div %</th><th className="r">Stock div %</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.period_end}>
                <td>{r.period_end}</td>
                <td className="r">{num(r.eps)}</td>
                <td className="r">{num(r.nav)}</td>
                <td className="r">{num(r.nocfps)}</td>
                <td className="r">{num(r.cash_dividend_pct, 1)}</td>
                <td className="r">{num(r.stock_dividend_pct, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Quarterly({ c }: { c: Company }) {
  if (c.quarterly_eps.length === 0) return null; // no interim results yet: an empty table says nothing
  return (
    <Card title="Quarterly EPS (un-audited, this financial year)">
      <div className="tablewrap" style={{ maxHeight: 300 }}>
        <table className="num">
          <thead><tr><th>Period end</th><th>Period</th><th className="r">EPS</th></tr></thead>
          <tbody>
            {c.quarterly_eps.slice(0, 16).map((q) => (
              <tr key={`${q.period_end}-${q.period}`}>
                <td>{q.period_end}</td>
                <td>{q.label}</td>
                <td className={`r ${q.eps < 0 ? "dn" : ""}`}>{num(q.eps)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Holding({ c }: { c: Company }) {
  const rows = c.shareholding.slice(0, 13);
  const latest = rows[0];
  const parts = latest
    ? ([
        ["Sponsor / director", latest.director, "#2563eb"],
        ["Government", latest.government, "#64748b"],
        ["Institute", latest.institute, "#f59e0b"],
        ["Foreign", latest.foreign, "#8b5cf6"],
        ["Public", latest.public, "#10b981"],
      ] as const)
    : [];
  return (
    <Card title="Shareholding">
      <p className="small mute" style={{ marginTop: 0 }}>The exchange publishes the year-end figures and the two most recent snapshots.</p>
      {latest ? (
        <>
          <div className="stack" role="img" aria-label={`Shareholding as of ${latest.as_of}`}>
            {parts.map(([label, v, color]) => (v ? <i key={label} style={{ width: `${v}%`, background: color }} title={`${label} ${v}%`} /> : null))}
          </div>
          <div className="row small" style={{ marginTop: 6 }}>
            {parts.map(([label, v, color]) => (
              <span key={label}><i className="sw" style={{ background: color }} /> {label} {num(v, 2)}%</span>
            ))}
          </div>
        </>
      ) : null}
      <div className="tablewrap" style={{ maxHeight: 280 }}>
        <table className="num small">
          <thead><tr><th>As of</th><th className="r">Sponsor</th><th className="r">Govt</th><th className="r">Institute</th><th className="r">Foreign</th><th className="r">Public</th></tr></thead>
          <tbody>
            {rows.map((s, i) => {
              const prev = rows[i + 1];
              const d = prev && s.director != null && prev.director != null ? s.director - prev.director : 0;
              return (
                <tr key={s.as_of}>
                  <td>{s.as_of}</td>
                  <td className={`r ${d > 0 ? "up" : d < 0 ? "dn" : ""}`}>{num(s.director)}</td>
                  <td className="r">{num(s.government)}</td>
                  <td className="r">{num(s.institute)}</td>
                  <td className="r">{num(s.foreign)}</td>
                  <td className="r">{num(s.public)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Yearly({ c }: { c: Company }) {
  const ys = c.financial_years.filter((y) => y.revenue != null || y.net_profit != null).slice(0, 6);
  if (!ys.length) return null;
  const rows: Array<[string, (y: (typeof ys)[number]) => string]> = [
    ["Revenue", (y) => cr(y.revenue)],
    ["Gross profit", (y) => cr(y.gross_profit)],
    ["Net profit", (y) => cr(y.net_profit)],
    ["Operating cash flow", (y) => cr(y.operating_cf)],
    ["Investing cash flow", (y) => cr(y.investing_cf)],
    ["Total assets", (y) => cr(y.total_assets)],
    ["Total equity", (y) => cr(y.total_equity)],
    ["Total debt", (y) => cr(y.total_debt)],
    ["Cash", (y) => cr(y.cash)],
    ["Interest expense", (y) => cr(y.interest_expense)],
  ];
  return (
    <Card title="Financial summary (BDT crore)">
      <div className="tablewrap">
        <table className="num">
          <thead><tr><th />{ys.map((y) => <th key={y.year} className="r">FY{y.year}</th>)}</tr></thead>
          <tbody>
            {rows.map(([label, f]) => (
              <tr key={label}><th scope="row">{label}</th>{ys.map((y) => <td key={y.year} className="r">{f(y)}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

const STATEMENT_LABEL = { income: "Profit & loss", balance_sheet: "Balance sheet", cash_flow: "Cash flow" } as const;
type Kind = keyof typeof STATEMENT_LABEL;

function Statements({ c }: { c: Company }) {
  const [kind, setKind] = useState<Kind>("income");
  if (!c.statements.length) return null;
  const st = c.statements.find((s) => s.kind === kind) ?? c.statements[0]!;
  const perShare = (label: string) => /per share|EPS|NAV|NOCFPS/i.test(label);
  return (
    <Card title="Financial statements">
      <Chips label="Statement" value={st.kind} onChange={setKind} options={c.statements.map((s) => ({ key: s.kind, label: STATEMENT_LABEL[s.kind] }))} />
      <div className="tablewrap" style={{ marginTop: 8 }}>
        <table className="num small">
          <thead><tr><th>BDT crore (per-share rows in Tk)</th>{st.years.map((y) => <th key={y} className="r">{y}</th>)}</tr></thead>
          <tbody>
            {st.rows.map((r) => (
              <tr key={r.label} className={r.total ? "strong" : undefined}>
                <th scope="row">{r.label}</th>
                {r.values.map((v, i) => (
                  <td key={st.years[i] ?? i} className={`r ${v != null && v < 0 ? "dn" : ""}`}>{v == null ? DASH : perShare(r.label) ? num(v) : num(v / 1e7, 2)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Insiders({ c }: { c: Company }) {
  if (!c.director_trades.length) return null;
  return (
    <Card title="Director buy and sell">
      <div className="tablewrap" style={{ maxHeight: 300 }}>
        <table className="num small">
          <thead><tr><th>Date</th><th>Holder</th><th>Side</th><th className="r">Shares</th><th className="r">Price</th></tr></thead>
          <tbody>
            {c.director_trades.slice(0, 30).map((t, i) => (
              <tr key={`${t.day}-${t.holder}-${i}`}>
                <td>{fmtDate(t.day)}</td>
                <td>{t.holder}</td>
                <td className={t.side === "Buy" ? "up" : t.side === "Sell" ? "dn" : ""}>{t.side}</td>
                <td className="r">{int(t.quantity)}</td>
                <td className="r">{num(t.price)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function News({ c }: { c: Company }) {
  if (!c.news.length) return null;
  return (
    <Card title="Company news (DSE disclosures)">
      <div className="tablewrap" style={{ maxHeight: 360 }}>
        <table>
          <tbody>
            {c.news.map((n, i) => (
              <tr key={`${n.day}-${i}`}>
                <td className="small mute" style={{ whiteSpace: "nowrap" }}>{fmtDate(n.day)}</td>
                <td><b>{n.title}</b><div className="small">{n.body}</div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/** Everything about the company beyond price: profile, health, history, statements, owners, news. */
export function CompanyDetails({ symbol }: { symbol: string }) {
  const q = useCompany(symbol);
  if (q.isPending) return <Card title="Company"><Loading onRetry={() => void q.refetch()} what={`Loading company details for ${symbol}`} /></Card>;
  if (q.isError) return <Card title="Company"><ErrorNotice error={q.error} onRetry={() => void q.refetch()} /></Card>;
  const c = q.data;
  return (
    <div data-agent="company" data-symbol={c.symbol}>
      <div className="grid2">
        <Health c={c} />
        <Overview c={c} />
      </div>
      <div style={{ marginTop: 16 }}>
        <PerShare c={c} />
      </div>
      <div className="grid2" style={{ marginBottom: 16 }}>
        <Quarterly c={c} />
        <Capital c={c} />
      </div>
      <Yearly c={c} />
      <Statements c={c} />
      <div className="grid2" style={{ marginBottom: 16 }}>
        <Holding c={c} />
        <Insiders c={c} />
      </div>
      <News c={c} />
      <p className="small mute">
        Company data fetched {fmtDate(c.fetched_at)} from{" "}
        {c.sources.map((s, i) => (
          <span key={s.name}>
            {i ? ", " : ""}
            <a href={s.url} target="_blank" rel="noreferrer">{s.name}</a>
            {s.ok ? "" : ` (unavailable: ${s.error ?? "error"})`}
          </span>
        ))}
        . Figures can differ between sources; check the company&apos;s own reports before acting.
      </p>
    </div>
  );
}
