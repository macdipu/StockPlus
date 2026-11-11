"""Render the analysis: HTML report (people), JSON knowledge file + Markdown brief (AI agents)."""
from __future__ import annotations

import json
import math
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from jinja2 import Template
from plotly.subplots import make_subplots

import config as C

DISCLAIMER = "For research only, not investment advice."


# --------------------------------------------------------------------------- plain-language summary
def _f(v, fmt="{:.2f}", none="n/a"):
    return none if v is None or (isinstance(v, float) and math.isnan(v)) else fmt.format(v)


def summarize(k: dict) -> list[str]:
    t, ind, sr, sig = k["trend"], k["indicators"], k["levels"], k["signal"]
    ch = t["changes"]
    lines = [k["candles"]["last_candle"]]
    pats = [p for p in k["candles"]["patterns"] if p["bars_ago"] <= 2]
    lines.append("Recent patterns: " + ", ".join(f"{p['pattern']} ({p['date']})" for p in pats) + "."
                 if pats else "No textbook candle pattern in the last 3 sessions.")
    above = [n for n, v in t["vs_ma"].items() if v and v["pct"] > 0]
    below = [n for n, v in t["vs_ma"].items() if v and v["pct"] < 0]
    lines.append(f"Price is above {', '.join(above) or 'none'} and below {', '.join(below) or 'none'} of its moving averages.")
    lines.append("Change: " + ", ".join(f"{p} {_f(v, '{:+.1f}%')}" for p, v in ch.items()) + ".")
    rsi = ind.get("rsi14")
    if rsi is not None:
        zone = "overbought" if rsi > 70 else "oversold" if rsi < 30 else "bullish" if rsi >= 50 else "bearish"
        lines.append(f"RSI {rsi:.0f} ({zone}); MACD is {'above' if ind['macd'] > ind['macd_signal'] else 'below'} "
                     f"its signal line; volume is {ind['vol_ratio']:.1f}× its 20-day average.")
    lines.append(f"Nearest support {_f(sr['below'][0] if sr['below'] else None)}, "
                 f"nearest resistance {_f(sr['above'][0] if sr['above'] else None)} "
                 f"(52-week range {sr['low_52w']:.2f}–{sr['high_52w']:.2f}).")
    pr = k["probability"]["similar_setups"]
    if pr["p_target_first"] is not None:
        lines.append(f"Signal: {sig['action']}. Historically, {pr['wins']}/{pr['n']} similar setups "
                     f"({pr['p_target_first']:.0%}) reached the target before the stop within "
                     f"{k['probability']['horizon_sessions']} sessions "
                     f"(target +{k['probability']['target_pct']:.1f}% vs stop −{k['probability']['stop_pct']:.1f}%; "
                     f"all-days baseline {_f(k['probability']['all_days_baseline']['p_target_first'], '{:.0%}')})"
                     + ("." if k["probability"]["reliable"] else " (too few samples to trust)."))
    else:
        lines.append(f"Signal: {sig['action']}. No comparable past setups to estimate a probability.")
    return lines


# --------------------------------------------------------------------------- JSON / Markdown for agents
def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return None if math.isnan(o) or math.isinf(o) else round(float(o), 4)
    if isinstance(o, (pd.Timestamp,)):
        return o.strftime("%Y-%m-%d")
    return o


def write_json(k: dict) -> str:
    os.makedirs(C.REPORT_DIR, exist_ok=True)
    path = os.path.join(C.REPORT_DIR, f"{k['symbol']}.json")
    with open(path, "w") as f:
        json.dump(_clean(k), f, indent=2, ensure_ascii=False)
    return path


def brief(k: dict) -> str:
    """Compact Markdown an AI agent can paste into its context."""
    p, fd, s, sig, pr = k["price"], k["fundamentals"], k["setup"], k["signal"], k["probability"]
    sim = pr["similar_setups"]
    plan = s["plan"]
    v = k["valuation"]
    out = [f"# {k['symbol']} — {k.get('name') or ''} (DSE, category {fd.get('category') or '?'})",
           f"As of {k['as_of']} · source {k['source']} · {DISCLAIMER}", "",
           "## Price",
           f"LTP {p['ltp']} ({_f(p['change_pct'], '{:+.2f}%')} vs prev close {p['prev_close']}), "
           f"O {p['open']} H {p['high']} L {p['low']}, volume {p['volume']:,.0f}; "
           f"52w {k['levels']['low_52w']}–{k['levels']['high_52w']}", "",
           "## Signal",
           f"**{sig['action']}** (net votes {sig['net_votes']:+d}; setup score {s['score']}/{s['max']})",
           "- Bullish: " + ("; ".join(sig["bullish_reasons"]) or "none"),
           "- Bearish: " + ("; ".join(sig["bearish_reasons"]) or "none"),
           f"- Plan: entry {plan['entry_zone'][0]}–{plan['entry_zone'][1]}, stop {plan['stop']} ({plan['stop_basis']}), "
           f"target {plan['target']} ({plan['target_basis']}), R/R {_f(plan['rr'])}"
           + ("" if plan["rr_ok"] else " ⚠ below 1.5"),
           f"- Short-term profit probability: {_f(sim['p_target_first'], '{:.0%}')} "
           f"(target +{pr['target_pct']:.1f}% before stop −{pr['stop_pct']:.1f}% within {pr['horizon_sessions']} sessions; "
           f"n={sim['n']}; baseline all days {_f(pr['all_days_baseline']['p_target_first'], '{:.0%}')}; "
           f"expectancy {_f(sim['expectancy_pct'], '{:+.2f}%')})"
           + ("" if pr["reliable"] else " ⚠ small sample"), "",
           "## Indicators",
           ", ".join(f"{key} {_f(val)}" for key, val in k["indicators"].items()), "",
           "## Candles (last 10 sessions)",
           "| date | O | H | L | C | V |", "|---|---|---|---|---|---|"]
    out += [f"| {r['date']} | {r['open']} | {r['high']} | {r['low']} | {r['close']} | {r['volume']:,.0f} |"
            for r in k["candles"]["last_sessions"]]
    out += ["", "Patterns: " + ("; ".join(f"{x['date']} {x['pattern']} ({x['direction']})"
                                          for x in k["candles"]["patterns"]) or "none"),
            "", "## Levels",
            f"Resistance above: {k['levels']['above'] or 'none'} · Support below: {k['levels']['below'] or 'none'}",
            "", "## Trend",
            ", ".join(f"{a} {_f(b, '{:+.1f}%')}" for a, b in k["trend"]["changes"].items()),
            "", "## Fundamentals"]
    for key in ("sector", "eps_ttm", "eps_ttm_basis", "eps_annual", "eps_q1", "eps_q2", "eps_q3",
                "eps_nine_months", "nav", "pe", "pe_dse_trailing", "market_cap", "total_shares", "sponsor_pct",
                "institute_pct", "foreign_pct", "public_pct", "free_float_pct", "last_dividend",
                "dividend_yield_pct"):
        out.append(f"- {key}: {fd.get(key)}")
    out += ["", "## Valuation (gap = fair value vs price)"]
    out += [f"- {r['method']}: {_f(r['fair_value'])} ({_f(r['gap_pct'], '{:+.0f}%')}) — {r['inputs']}" for r in v["rows"]]
    out += [f"- note: {n}" for n in v["notes"]]
    out += ["", "## Summary"] + [f"- {x}" for x in k["summary"]]
    out += ["", "## Recent announcements"] + [f"- {n['date']} — {n['title']}: {n['text'][:240]}" for n in k["news"][:8]]
    return "\n".join(out) + "\n"


def write_brief(k: dict) -> str:
    os.makedirs(C.REPORT_DIR, exist_ok=True)
    path = os.path.join(C.REPORT_DIR, f"{k['symbol']}.md")
    with open(path, "w") as f:
        f.write(brief(k))
    return path


# --------------------------------------------------------------------------- HTML
def chart(ind: pd.DataFrame, pats: list[dict], sr: dict) -> go.Figure:
    d = ind.iloc[-C.CHART_BARS:]
    x = d.index.strftime("%Y-%m-%d")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(x=x, open=d["open"], high=d["high"], low=d["low"], close=d["close"],
                                 name="OHLC", increasing_line_color="#16a34a", decreasing_line_color="#dc2626"),
                  row=1, col=1)
    for col, color, dash in (("sma20", "#2563eb", None), ("sma50", "#f59e0b", None), ("sma200", "#7c3aed", None),
                             ("ema9", "#06b6d4", "dot"), ("ema21", "#ec4899", "dot")):
        fig.add_trace(go.Scatter(x=x, y=d[col], name=col.upper(), line=dict(color=color, width=1.2, dash=dash)),
                      row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=d["bb_upper"], name="BB upper", line=dict(color="#94a3b8", width=0.8),
                             visible="legendonly"), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=d["bb_lower"], name="BB lower", line=dict(color="#94a3b8", width=0.8),
                             visible="legendonly"), row=1, col=1)

    for direction, sym, color, ykey, off in (("bullish", "triangle-up", "#16a34a", "low", 0.985),
                                             ("bearish", "triangle-down", "#dc2626", "high", 1.015),
                                             ("neutral", "circle", "#64748b", "high", 1.015)):
        ps = [p for p in pats if p["direction"] == direction]
        if ps:
            fig.add_trace(go.Scatter(x=[p["date"] for p in ps], y=[p[ykey] * off for p in ps], mode="markers",
                                     marker=dict(symbol=sym, size=11, color=color), name=f"{direction} pattern",
                                     text=[p["pattern"] for p in ps], hovertemplate="%{text}<extra></extra>"),
                          row=1, col=1)
    for lv in sr["above"]:
        fig.add_hline(y=lv, line=dict(color="#dc2626", dash="dash", width=1), annotation_text=f"R {lv}", row=1, col=1)
    for lv in sr["below"]:
        fig.add_hline(y=lv, line=dict(color="#16a34a", dash="dash", width=1), annotation_text=f"S {lv}", row=1, col=1)

    colors = np.where(d["close"] >= d["open"], "#16a34a", "#dc2626")
    fig.add_trace(go.Bar(x=x, y=d["volume"], marker_color=colors, name="Volume", opacity=0.6), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=d["vol_avg20"], name="Vol avg 20", line=dict(color="#0f172a", width=1)),
                  row=2, col=1)
    fig.update_xaxes(type="category", nticks=12, rangeslider_visible=False)
    fig.update_layout(height=720, margin=dict(l=40, r=20, t=30, b=30), template="plotly_white",
                      legend=dict(orientation="h", y=1.04))
    return fig


TEMPLATE = Template("""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{{k.symbol}} analysis</title>
<style>
body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:1200px;margin:0 auto;padding:16px;color:#0f172a;background:#fff}
h1{margin-bottom:0}.sub{color:#64748b;margin-top:4px}table{border-collapse:collapse;width:100%;margin:8px 0 20px;font-size:14px}
th,td{border-bottom:1px solid #e2e8f0;padding:6px 8px;text-align:left;vertical-align:top}th{background:#f8fafc}
.pos{color:#16a34a}.neg{color:#dc2626}.pill{display:inline-block;padding:4px 12px;border-radius:999px;font-weight:700;color:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}.warn{color:#b45309}
footer{margin-top:32px;padding-top:12px;border-top:1px solid #e2e8f0;color:#64748b;font-size:13px}
</style></head><body>
<h1>{{k.symbol}} <small>{{k.name or ''}}</small></h1>
<p class="sub">Category {{f.category or '?'}} · LTP <b>{{k.price.ltp}}</b>
{% if k.price.change_pct is not none %}(<span class="{{'pos' if k.price.change_pct>=0 else 'neg'}}">{{'%+.2f'|format(k.price.change_pct)}}%</span>){% endif %}
· as of {{k.as_of}}</p>
<p><span class="pill" style="background:{{color}}">{{k.signal.action}}</span>
 Setup score {{k.setup.score}}/{{k.setup.max}} · net votes {{'%+d'|format(k.signal.net_votes)}}
{% if prob.p_target_first is not none %} · short-term hit rate {{'%.0f'|format(prob.p_target_first*100)}}% (n={{prob.n}}){% endif %}</p>
{{chart}}
<h2>Summary</h2><ul>{% for s in k.summary %}<li>{{s}}</li>{% endfor %}</ul>
<div class="grid"><div><h2>Trend</h2><table>
{% for p,v in k.trend.changes.items() %}<tr><th>{{p}}</th><td class="{{'pos' if v and v>=0 else 'neg'}}">{{'%+.1f%%'|format(v) if v is not none else 'n/a'}}</td></tr>{% endfor %}
{% for n,v in k.trend.vs_ma.items() %}<tr><th>vs {{n}}</th><td>{% if v %}{{'%.2f'|format(v.value)}} (<span class="{{'pos' if v.pct>=0 else 'neg'}}">{{'%+.1f'|format(v.pct)}}%</span>){% else %}n/a{% endif %}</td></tr>{% endfor %}
</table></div>
<div><h2>Indicators</h2><table>{% for n,v in k.indicators.items() %}<tr><th>{{n}}</th><td>{{'%.2f'|format(v) if v is not none else 'n/a'}}</td></tr>{% endfor %}</table></div>
<div><h2>Support / resistance</h2><table>
{% for r in k.levels.above|reverse %}<tr><th class="neg">R</th><td>{{r}}</td></tr>{% endfor %}
<tr><th>Price</th><td><b>{{k.levels.price}}</b></td></tr>
{% for s in k.levels.below %}<tr><th class="pos">S</th><td>{{s}}</td></tr>{% endfor %}
<tr><th>52w high / low</th><td>{{k.levels.high_52w}} / {{k.levels.low_52w}}</td></tr></table></div></div>
<h2>Candlestick patterns (last {{cfg.PATTERN_LOOKBACK}} sessions)</h2>
<table><tr><th>Date</th><th>Pattern</th><th>Direction</th></tr>
{% for p in k.candles.patterns|reverse %}<tr><td>{{p.date}}</td><td>{{p.pattern}}</td><td class="{{'pos' if p.direction=='bullish' else 'neg' if p.direction=='bearish' else ''}}">{{p.direction}}</td></tr>
{% else %}<tr><td colspan="3">None detected</td></tr>{% endfor %}</table>
<h2>Fundamentals</h2><table>
{% for label,key in fund_rows %}<tr><th>{{label}}</th><td>{{f.get(key) if f.get(key) is not none else 'n/a'}}</td></tr>{% endfor %}</table>
<h2>Fair value</h2><table><tr><th>Method</th><th>Inputs</th><th>Fair value</th><th>vs price</th></tr>
{% for r in k.valuation.rows %}<tr><td>{{r.method}}</td><td>{{r.inputs}}</td><td>{{'%.2f'|format(r.fair_value) if r.fair_value else 'n/a'}}</td>
<td class="{{'pos' if r.gap_pct and r.gap_pct>=0 else 'neg'}}">{{'%+.1f%%'|format(r.gap_pct) if r.gap_pct is not none else 'n/a'}}</td></tr>{% endfor %}</table>
<ul>{% for n in k.valuation.notes %}<li>{{n}}</li>{% endfor %}</ul>
<h2>Short-term trade setup</h2><table>
{% for c in k.setup.checks %}<tr><th>{{c.label}}</th><td class="{{'pos' if c.pass else 'neg'}}">{{'✔' if c.pass else '✘'}}</td></tr>{% endfor %}
<tr><th>Entry zone</th><td>{{plan.entry_zone[0]}} – {{plan.entry_zone[1]}}</td></tr>
<tr><th>Stop-loss</th><td>{{plan.stop}} ({{plan.stop_basis}}, −{{'%.1f'|format(plan.risk_pct)}}%)</td></tr>
<tr><th>Target</th><td>{{plan.target}} ({{plan.target_basis}}, +{{'%.1f'|format(plan.reward_pct)}}%)</td></tr>
<tr><th>Risk / reward</th><td class="{{'pos' if plan.rr_ok else 'neg'}}">{{'%.2f'|format(plan.rr) if plan.rr else 'n/a'}}{% if not plan.rr_ok %} — below 1.5{% endif %}</td></tr>
</table>{% for fl in k.setup.flags %}<p class="warn">⚠ {{fl}}</p>{% endfor %}
<h2>Signal reasoning</h2><div class="grid"><div><b class="pos">Bullish</b><ul>{% for r in k.signal.bullish_reasons %}<li>{{r}}</li>{% endfor %}</ul></div>
<div><b class="neg">Bearish</b><ul>{% for r in k.signal.bearish_reasons %}<li>{{r}}</li>{% endfor %}</ul></div></div>
<p class="sub">{{k.signal.rule}}</p>
<h2>Short-term profit probability</h2><table><tr><th></th><th>Similar setups</th><th>All days (baseline)</th></tr>
{% for label,key,fmt in prob_rows %}<tr><th>{{label}}</th>
{% for blk in (k.probability.similar_setups, k.probability.all_days_baseline) %}<td>{{fmt|format(blk[key]) if blk[key] is not none else 'n/a'}}</td>{% endfor %}</tr>{% endfor %}</table>
<p class="sub">{{k.probability.method}}</p>{% if k.probability.warning %}<p class="warn">⚠ {{k.probability.warning}}</p>{% endif %}
<h2>Recent news</h2><table>{% for n in k.news %}<tr><td style="white-space:nowrap">{{n.date}}</td><td><b>{{n.title}}</b><br>{{n.text}}</td></tr>{% endfor %}</table>
<footer>{{disclaimer}} Data: {{k.source}}, fetched {{k.as_of}}.</footer></body></html>""")

FUND_ROWS = [("Sector", "sector"), ("LTP", "ltp"), ("EPS TTM", "eps_ttm"), ("EPS basis", "eps_ttm_basis"),
             ("EPS annual", "eps_annual"), ("EPS Q1", "eps_q1"), ("EPS Q2", "eps_q2"), ("EPS Q3", "eps_q3"),
             ("EPS 9M", "eps_nine_months"), ("NAV / share", "nav"), ("P/E (ours, TTM)", "pe"),
             ("P/E (DSE trailing)", "pe_dse_trailing"), ("Market cap", "market_cap"), ("Total shares", "total_shares"),
             ("Sponsor %", "sponsor_pct"), ("Institute %", "institute_pct"), ("Foreign %", "foreign_pct"),
             ("Public %", "public_pct"), ("Free float %", "free_float_pct"), ("Category", "category"),
             ("Last dividend", "last_dividend"), ("Dividend yield %", "dividend_yield_pct")]
PROB_ROWS = [("Samples", "n", "%d"), ("Hit target first", "p_target_first", "%.2f"), ("Wins", "wins", "%d"),
             ("Losses", "losses", "%d"), ("Unresolved", "unresolved", "%d"),
             ("Avg fwd return %", "avg_fwd_return_pct", "%+.2f"), ("% positive fwd", "pct_positive_fwd", "%.0f"),
             ("Expectancy %", "expectancy_pct", "%+.2f")]
COLORS = {"STRONG BUY": "#15803d", "BUY": "#16a34a", "HOLD": "#64748b", "SELL": "#dc2626",
          "STRONG SELL": "#991b1b", "AVOID": "#0f172a"}


def write_html(k: dict, ind: pd.DataFrame) -> str:
    os.makedirs(C.REPORT_DIR, exist_ok=True)
    fig = chart(ind, k["candles"]["patterns"], k["levels"])
    f = {key: (round(v, 2) if isinstance(v, float) else v) for key, v in k["fundamentals"].items()}
    html = TEMPLATE.render(k=_clean(k), f=f, chart=fig.to_html(full_html=False, include_plotlyjs="cdn"),
                           fund_rows=FUND_ROWS, prob_rows=PROB_ROWS, plan=k["setup"]["plan"],
                           prob=k["probability"]["similar_setups"], color=COLORS.get(k["signal"]["action"], "#64748b"),
                           cfg=C, disclaimer=DISCLAIMER)
    path = os.path.join(C.REPORT_DIR, f"{k['symbol']}.html")
    with open(path, "w") as fh:
        fh.write(html)
    return path
