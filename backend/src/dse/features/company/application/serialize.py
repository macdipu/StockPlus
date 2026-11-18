"""Dossier entity → plain JSON (what the API returns and the cache stores)."""

import dataclasses
from datetime import date
from typing import Any

from dse.features.company.domain import insights
from dse.features.company.domain.entities import CompanyDossier

QUARTER_LABEL = {"q1": "Q1", "q2": "Q2", "q3": "Q3", "h1": "Half year", "9m": "Nine months"}


def _plain(o: Any) -> Any:
    if dataclasses.is_dataclass(o) and not isinstance(o, type):
        return {f.name: _plain(getattr(o, f.name)) for f in dataclasses.fields(o)}
    if isinstance(o, list | tuple):
        return [_plain(v) for v in o]
    if isinstance(o, date):
        return o.isoformat()
    return o


def dossier_to_dict(d: CompanyDossier) -> dict[str, Any]:
    """Price-independent part of the dossier. `with_price` adds the price-dependent ratios at read time."""
    sn, am, ts = d.exchange, d.amarstock, d.topstock
    by_year: dict[str, dict[str, Any]] = {}
    for key, series in (("eps", sn.eps_annual), ("nav", sn.nav), ("nocfps", sn.nocfps)):
        for pv in series:
            by_year.setdefault(pv.period_end, {"period_end": pv.period_end})[key] = pv.value
    for dv in sn.dividends:
        row = by_year.setdefault(dv.period_end, {"period_end": dv.period_end})
        row["cash_dividend_pct"], row["stock_dividend_pct"] = dv.cash_pct, dv.stock_pct
    for y in ts.years:  # cash flow per share comes from TopStock's yearly figures, matched to the fiscal year
        found: dict[str, Any] | None = next((r for e, r in by_year.items() if e[:4] == str(y.year)), None)
        if found is not None and y.nocfps is not None:
            found["nocfps"] = y.nocfps
    annual_ends = {pv.period_end for pv in sn.eps_annual} | {dv.period_end for dv in sn.dividends}
    return {
        "symbol": d.symbol,
        "fetched_at": d.fetched_at,
        "profile": {
            "contact": _plain(sn.contact),
            "listing_year": sn.listing_year,
            "year_end": sn.year_end,
            "operational_status": sn.operational_status,
            "credit_rating": _plain(ts.rating),
        },
        "capital": {**_plain(sn.capital), "total_loan_mn": sn.capital.total_loan_mn},
        "per_share_history": sorted(
            (r for e, r in by_year.items() if e in annual_ends), key=lambda r: r["period_end"], reverse=True
        ),
        "nav_history": [_plain(v) for v in sorted(sn.nav, key=lambda v: v.period_end, reverse=True)],
        "quarterly_eps": [
            {**_plain(q), "label": QUARTER_LABEL.get(q.period, q.period)}
            for q in sorted(sn.eps_quarterly, key=lambda q: (q.period_end, q.period), reverse=True)
        ],
        "dividends": [
            {**_plain(x), "year": x.year, "cash_per_share": round(x.cash_pct / 100 * insights.FACE_VALUE, 2)}
            for x in sorted(sn.dividends, key=lambda x: x.period_end, reverse=True)
        ],
        "shareholding": [_plain(s) for s in sorted(sn.shareholding, key=lambda s: s.as_of, reverse=True)],
        "financial_years": [_plain(y) for y in sorted(ts.years, key=lambda y: y.year, reverse=True)],
        "statements": [_plain(s) for s in am.statements],
        "director_trades": [_plain(t) for t in am.director_trades],
        "events": _plain(d.events),
        "news": [_plain(n) for n in sn.news],
        "sources": [_plain(s) for s in d.sources],
        "units": {
            "capital": "BDT million (total_shares is a count)",
            "financial_years": "BDT; eps, nav_per_share, nocfps are Tk per share",
            "statements": "BDT as reported; per-share rows in Tk",
            "dividends": "% of the Tk 10 face value; cash_per_share in Tk",
        },
    }


def with_price(base: dict[str, Any], d: CompanyDossier, price: float | None) -> dict[str, Any]:
    return {
        **base,
        "price": price,
        "ratios": [_plain(r) for r in insights.ratios(d, price)],
        "flags": [_plain(f) for f in insights.flags(d, price)],
    }
