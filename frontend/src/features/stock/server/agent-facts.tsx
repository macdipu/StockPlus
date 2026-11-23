/**
 * Server-rendered, machine-readable facts for one share. It is in the HTML before any JavaScript runs, so a
 * crawler or an AI agent that only fetches the page still gets the numbers: a semantic <dl> with stable
 * `data-field` names, plus the same facts as schema.org JSON-LD. Full data: the JSON links it lists.
 */

const API_ORIGIN = process.env.API_ORIGIN ?? "http://localhost:8001";
const API = `${API_ORIGIN}/api/v1`;

type Json = Record<string, unknown>;

async function get(path: string, ms: number): Promise<Json | null> {
  try {
    const r = await fetch(`${API}${path}`, { cache: "no-store", signal: AbortSignal.timeout(ms), headers: { Accept: "application/json" } });
    if (!r.ok) return null;
    const body = (await r.json()) as { data?: Json };
    return body.data ?? null;
  } catch {
    return null;
  }
}

const n = (v: unknown, d = 2) => (typeof v === "number" && Number.isFinite(v) ? Number(v.toFixed(d)) : null);
const at = (o: unknown, ...path: string[]): unknown => path.reduce<unknown>((x, k) => (x && typeof x === "object" ? (x as Json)[k] : undefined), o);

export interface Fact {
  field: string;
  label: string;
  value: string | number | null;
  unit?: string;
}

export async function loadFacts(symbol: string): Promise<{ facts: Fact[]; plan: Array<{ step: string; text: string }>; headline: string | null; name: string | null; flags: string[] } | null> {
  const [a, c] = await Promise.all([get(`/stocks/${encodeURIComponent(symbol)}/analysis`, 5000), get(`/stocks/${encodeURIComponent(symbol)}/company`, 5000)]);
  if (!a) return null;
  const ratio = (key: string) => {
    const r = (c?.ratios as Json[] | undefined)?.find((x) => x.key === key);
    return r ? n(r.value) : null;
  };
  const plan = (at(a, "candle_story", "plan") as Array<{ step: string; text: string }> | undefined) ?? [];
  const ann = (at(a, "candle_story", "annotations") as Json[] | undefined) ?? [];
  const entry = ann.find((x) => x.kind === "entry");
  const stop = ann.find((x) => x.kind === "stop");
  const target = ann.find((x) => x.kind === "target");
  const facts: Fact[] = [
    { field: "symbol", label: "Trading code", value: symbol },
    { field: "sector", label: "Sector", value: (at(a, "fundamentals", "sector") as string) ?? null },
    { field: "category", label: "Category", value: (at(a, "fundamentals", "category") as string) ?? null },
    { field: "price", label: "Last price", value: n(at(a, "price", "ltp")), unit: "BDT" },
    { field: "change_pct", label: "Change today", value: n(at(a, "price", "change_pct")), unit: "%" },
    { field: "as_of", label: "As of", value: (at(a, "as_of") as string) ?? null },
    { field: "signal", label: "Signal", value: (at(a, "signal", "action") as string) ?? null },
    { field: "setup_score", label: "Setup score", value: n(at(a, "setup", "score"), 0) },
    { field: "buy_zone_low", label: "Buy zone low", value: n(entry?.price_to), unit: "BDT" },
    { field: "buy_zone_high", label: "Buy zone high", value: n(entry?.price), unit: "BDT" },
    { field: "stop", label: "Stop (exit below)", value: n(stop?.price), unit: "BDT" },
    { field: "target", label: "Target", value: n(target?.price), unit: "BDT" },
    { field: "rsi14", label: "RSI 14", value: n(at(a, "indicators", "rsi14"), 1) },
    { field: "pe", label: "P/E (TTM)", value: n(at(a, "fundamentals", "pe"), 1) },
    { field: "eps_ttm", label: "EPS (TTM)", value: n(at(a, "fundamentals", "eps_ttm")), unit: "BDT" },
    { field: "nav", label: "NAV per share", value: n(at(a, "fundamentals", "nav")), unit: "BDT" },
    { field: "pb", label: "Price / book", value: ratio("pb") },
    { field: "dividend_yield", label: "Dividend yield", value: ratio("dividend_yield"), unit: "%" },
    { field: "roe", label: "Return on equity", value: ratio("roe"), unit: "%" },
    { field: "debt_to_equity", label: "Debt / equity", value: ratio("debt_to_equity") ?? ratio("loan_to_equity") },
    { field: "high_52w", label: "52-week high", value: n(at(a, "levels", "high_52w")), unit: "BDT" },
    { field: "low_52w", label: "52-week low", value: n(at(a, "levels", "low_52w")), unit: "BDT" },
    { field: "record_date", label: "Record date", value: (at(c, "events", "record_date") as string) ?? null },
    { field: "credit_rating", label: "Credit rating", value: (at(c, "profile", "credit_rating", "long_term") as string) ?? null },
  ];
  return {
    facts,
    plan,
    headline: (at(a, "candle_story", "headline") as string) ?? null,
    name: (at(a, "name") as string) ?? null,
    flags: ((c?.flags as Json[] | undefined) ?? []).map((f) => String(f.text)),
  };
}

export async function AgentFacts({ symbol }: { symbol: string }) {
  const data = await loadFacts(symbol);
  if (!data) return null;
  const { facts, plan, headline, name, flags } = data;
  const ld = {
    "@context": "https://schema.org",
    "@type": "Corporation",
    name: name ?? symbol,
    tickerSymbol: `DSE:${symbol}`,
    additionalProperty: facts
      .filter((f) => f.value != null)
      .map((f) => ({ "@type": "PropertyValue", propertyID: f.field, name: f.label, value: f.value, ...(f.unit ? { unitText: f.unit } : {}) })),
    subjectOf: [
      { "@type": "Dataset", name: `${symbol} analysis (JSON)`, url: `/api/v1/stocks/${symbol}/analysis` },
      { "@type": "Dataset", name: `${symbol} company details (JSON)`, url: `/api/v1/stocks/${symbol}/company` },
      { "@type": "DigitalDocument", name: `${symbol} brief (Markdown)`, url: `/api/v1/stocks/${symbol}/brief` },
    ],
  };
  return (
    <section className="card facts" aria-label="Key facts" data-agent="stock-facts" data-symbol={symbol}>
      <details>
      <summary><b>Key facts and data links</b> <span className="small mute">{name ?? symbol}: the numbers in one list, and the machine-readable data</span></summary>
      {headline ? <p data-field="headline" style={{ marginTop: 0 }}>{headline}</p> : null}
      <dl>
        {facts.map((f) => (
          <div key={f.field} data-field={f.field}>
            <dt>{f.label}</dt>
            <dd>{f.value ?? "–"}{f.value != null && f.unit === "%" ? "%" : ""}</dd>
          </div>
        ))}
      </dl>
      {plan.length ? (
        <details style={{ marginTop: 8 }}>
          <summary className="small">Trade plan and company flags (text)</summary>
          <ul className="plain small" data-agent="plan">
            {plan.map((p) => <li key={p.step} data-field={p.step}><b>{p.step}:</b> {p.text}</li>)}
          </ul>
          <ul className="plain small" data-agent="flags">
            {flags.map((t) => <li key={t}>{t}</li>)}
          </ul>
        </details>
      ) : null}
      <p className="small mute" style={{ marginBottom: 0 }}>
        Machine-readable: <a href={`/api/v1/stocks/${symbol}/analysis`}>analysis.json</a> · <a href={`/api/v1/stocks/${symbol}/company`}>company.json</a> ·{" "}
        <a href={`/api/v1/stocks/${symbol}/brief`}>brief.md</a> · <a href="/llms.txt">llms.txt</a>
      </p>
      </details>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(ld).replace(/</g, "\\u003c") }} />
    </section>
  );
}
