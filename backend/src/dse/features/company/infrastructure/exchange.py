"""Map the exchange's company data (as the market_data facade serves it) to the dossier's exchange part.

Pure functions over plain dicts (`ProfileDto.model_dump()`), so no other feature's types are imported.
"""

import calendar
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

from dse.features.company.domain.entities import (
    Capital,
    Contact,
    DividendRecord,
    Events,
    ExchangePart,
    NewsItem,
    PeriodValue,
    QuarterlyEps,
    Shareholding,
)

_MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
_QUARTERS = (
    ("q1", "eps_q1"),
    ("q2", "eps_q2"),
    ("q3", "eps_q3"),
    ("half", "eps_half_year"),
    ("nine", "eps_nine_months"),
)
_LABEL = {"half": "h1", "nine": "9m"}


def _month_end(year: int, month: int) -> str:
    return date(year, month, calendar.monthrange(year, month)[1]).isoformat()


def fiscal_period_end(year: int, year_end_month: str | None) -> str:
    """The exchange reports a fiscal year by its number; the period ends in the company's year-end month."""
    month = _MONTHS.get((year_end_month or "december").strip().lower(), 12)
    return _month_end(year, month)


def _yyyymm(v: str) -> str | None:
    if len(v) == 6 and v.isdigit():
        return _month_end(int(v[:4]), int(v[4:]))
    return None


def _iso(v: Any) -> str | None:
    """dd-mm-yyyy -> ISO; anything else is returned as given."""
    s = str(v).strip() if v else ""
    if not s:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return s


def _val(v: Any) -> float | None:
    return float(v) if isinstance(v, int | float) and not isinstance(v, bool) else None


def exchange_part(profile: Mapping[str, Any], announcements: Sequence[Mapping[str, Any]]) -> ExchangePart:
    f: Mapping[str, Any] = profile.get("fundamentals") or {}
    info: Mapping[str, Any] = f.get("info") or {}
    month = f.get("year_end")
    years = sorted(f.get("year_history") or [], key=lambda y: y["year"])
    eps = tuple(
        PeriodValue(fiscal_period_end(y["year"], month), v)
        for y in years
        if (v := _val(y.get("eps"))) is not None
    )
    nav = tuple(
        PeriodValue(fiscal_period_end(y["year"], month), v)
        for y in years
        if (v := _val(y.get("nav"))) is not None
    )
    ends: Mapping[str, str] = f.get("eps_period_ends") or {}
    quarterly = tuple(
        QuarterlyEps(end, _LABEL.get(key, key), v)
        for key, field in _QUARTERS
        if (end := _yyyymm(ends.get(key, ""))) and (v := _val(f.get(field))) is not None
    )
    dividends = tuple(
        DividendRecord(
            fiscal_period_end(d["year"], month), float(d.get("cash_pct") or 0), float(d.get("stock_pct") or 0)
        )
        for d in sorted(f.get("dividends") or [], key=lambda d: d["year"])
    )
    holdings = tuple(
        Shareholding(
            as_of=str(h["as_of"]),
            director=_val(h.get("sponsor_pct")),
            government=_val(h.get("government_pct")),
            institute=_val(h.get("institution_pct")),
            foreign=_val(h.get("foreign_pct")),
            public=_val(h.get("public_pct")),
        )
        for h in f.get("holding_history") or []
        if h.get("as_of")
    )
    paid_up = _val(f.get("paid_up_capital"))
    secretary = " · ".join(x for x in (info.get("secretary_name"), info.get("secretary_email")) if x) or None
    return ExchangePart(
        contact=Contact(
            address=info.get("head_office"),
            registered_office=info.get("registered_office"),
            factory_address=info.get("factory_address"),
            secretary=secretary,
            phone=info.get("phone"),
            fax=info.get("fax"),
            email=info.get("email"),
            website=info.get("website"),
        ),
        listing_year=f.get("listing_year"),
        year_end=month,
        operational_status=info.get("operational_status"),
        capital=Capital(
            authorized_mn=_val(info.get("authorized_capital_mn")),
            paid_up_mn=paid_up / 1e6 if paid_up is not None else None,
            reserve_mn=_val(info.get("reserve_mn")),
            long_term_loan_mn=_val(info.get("long_term_loan_mn")),
            short_term_loan_mn=_val(info.get("short_term_loan_mn")),
            total_shares=f.get("total_shares"),
            loans_as_of=None,
        ),
        eps_annual=eps,
        eps_quarterly=quarterly,
        nav=nav,
        nocfps=(),
        dividends=dividends,
        shareholding=holdings,
        events=Events(last_agm=_iso(info.get("agm_date"))),
        news=tuple(
            NewsItem(
                day=date.fromisoformat(a["published_on"]) if a.get("published_on") else None,
                title=a.get("title") or a.get("kind") or "Announcement",
                body=a.get("body") or "",
            )
            for a in announcements
        ),
    )
