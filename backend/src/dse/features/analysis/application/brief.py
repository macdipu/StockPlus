"""Compact Markdown an AI agent can paste into its context (legacy `report.brief`)."""

from typing import Any

from dse.features.analysis.domain.summary import fmt


def render_brief(k: dict[str, Any]) -> str:
    p, fd, s, sig, pr = k["price"], k["fundamentals"], k["setup"], k["signal"], k["probability"]
    sim = pr["similar_setups"]
    plan = s["plan"]
    v = k["valuation"]
    out = [
        f"# {k['symbol']} — {k.get('name') or ''} (DSE, category {fd.get('category') or '?'})",
        f"As of {k['as_of']} · {k['disclaimer']}",
        "",
        "## Price",
        f"LTP {p['ltp']} ({fmt(p['change_pct'], '{:+.2f}%')} vs prev close {p['prev_close']}), "
        f"O {p['open']} H {p['high']} L {p['low']}, volume {p['volume']:,.0f}; "
        f"52w {k['levels']['low_52w']}–{k['levels']['high_52w']}",
        "",
        "## Signal",
        f"**{sig['action']}** (net votes {sig['net_votes']:+d}; setup score {s['score']}/{s['max']})",
        "- Bullish: " + ("; ".join(sig["bullish_reasons"]) or "none"),
        "- Bearish: " + ("; ".join(sig["bearish_reasons"]) or "none"),
        f"- Plan: entry {plan['entry_zone'][0]}–{plan['entry_zone'][1]}, stop {plan['stop']} "
        f"({plan['stop_basis']}), target {plan['target']} ({plan['target_basis']}), R/R {fmt(plan['rr'])}"
        + ("" if plan["rr_ok"] else " ⚠ below 1.5"),
        f"- Short-term profit probability: {fmt(sim['p_target_first'], '{:.0%}')} "
        f"(target +{pr['target_pct']:.1f}% before stop −{pr['stop_pct']:.1f}% within "
        f"{pr['horizon_sessions']} sessions; n={sim['n']}; baseline all days "
        f"{fmt(pr['all_days_baseline']['p_target_first'], '{:.0%}')}; "
        f"expectancy {fmt(sim['expectancy_pct'], '{:+.2f}%')})"
        + ("" if pr["reliable"] else " ⚠ small sample"),
        "",
        "## Indicators",
        ", ".join(f"{key} {fmt(val)}" for key, val in k["indicators"].items()),
        "",
        "## Candles (last 10 sessions)",
        "| date | O | H | L | C | V |",
        "|---|---|---|---|---|---|",
    ]
    out += [
        f"| {r['date']} | {r['open']} | {r['high']} | {r['low']} | {r['close']} | {r['volume']:,.0f} |"
        for r in k["candles"]["last_sessions"]
    ]
    out += [
        "",
        "Patterns: "
        + (
            "; ".join(f"{x['date']} {x['pattern']} ({x['direction']})" for x in k["candles"]["patterns"])
            or "none"
        ),
        "",
        "## Levels",
        f"Resistance above: {k['levels']['above'] or 'none'} · "
        f"Support below: {k['levels']['below'] or 'none'}",
        "",
        "## Trend",
        ", ".join(f"{a} {fmt(b, '{:+.1f}%')}" for a, b in k["trend"]["changes"].items()),
        "",
        "## Fundamentals",
    ]
    for key in (
        "sector",
        "eps_ttm",
        "eps_ttm_basis",
        "eps_annual",
        "eps_q1",
        "eps_q2",
        "eps_q3",
        "eps_nine_months",
        "nav",
        "pe",
        "pe_dse_trailing",
        "market_cap",
        "total_shares",
        "free_float_pct",
        "dividend_per_share",
        "dividend_yield_pct",
    ):
        out.append(f"- {key}: {fd.get(key)}")
    out += ["", "## Valuation (gap = fair value vs price)"]
    out += [
        f"- {r['method']}: {fmt(r['fair_value'])} ({fmt(r['gap_pct'], '{:+.0f}%')}) — {r['inputs']}"
        for r in v["rows"]
    ]
    out += [f"- note: {n}" for n in v["notes"]]
    out += ["", "## Summary"] + [f"- {x}" for x in k["summary"]]
    out += ["", "## Recent announcements"] + [
        f"- {n['date']} — {n['title']}: {n['text'][:240]}" for n in k["news"][:8]
    ]
    return "\n".join(out) + "\n"
