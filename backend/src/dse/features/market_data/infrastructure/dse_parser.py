"""Parse www.dse.com.bd payloads into domain entities. Pure functions; every shape assumption lives here.

* /company/{SYM}: Next.js React-Server-Components "flight" chunks embedded in the HTML carry
  {"company": {...}, "series": [{date, open, high, low, price, volume, trades}, ...]}.
* /api/live/snapshot: {"market": {...session, totals.tradeTime...},
                       "prices": {"cols": [...], "rows": [[...]]}}.
"""

import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from dse.features.market_data.domain.entities import (
    FUNDAMENTALS_SCHEMA,
    Announcement,
    BarSource,
    CompanyInfo,
    CompanyPage,
    DailyBar,
    Dividend,
    EpsReport,
    Fundamentals,
    Instrument,
    MarketSnapshot,
    Quote,
    ShareholdingPattern,
    YearFinancial,
)
from dse.shared_kernel.errors import NotFoundError, UpstreamUnavailableError
from dse.shared_kernel.symbol import Symbol

_FLIGHT_PUSH = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)\s*</script>', re.S)
EPS_METRICS = ("EPS - Continuing Operations Basic", "Earnings Per Share (EPS) Basic")


def _undefined_to_none(o: Any) -> Any:
    if isinstance(o, dict):
        return {k: _undefined_to_none(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_undefined_to_none(v) for v in o]
    return None if o == "$undefined" else o


def extract_flight(html: str) -> dict[str, Any]:
    chunks = _FLIGHT_PUSH.findall(html)
    if not chunks:
        raise UpstreamUnavailableError("DSE page has no Next.js flight payload — page format changed")
    text = "".join(json.loads(f'"{c}"') for c in chunks)
    dec = json.JSONDecoder()
    out: dict[str, Any] = {}
    for key in ("company", "series"):
        m = re.search(rf'"{key}":\s*([\[{{])', text)
        if m:
            out[key], _ = dec.raw_decode(text, m.start(1))
    return dict(_undefined_to_none(out))


def _f(v: Any) -> float | None:
    try:
        return None if v is None or v == "" else float(v)
    except (TypeError, ValueError):
        return None


def _dec(v: Any) -> Decimal:
    return Decimal(str(v))


def _day(text: str | None) -> date | None:
    for fmt in ("%d %b %Y", "%Y-%m-%d", "%b %d, %Y"):
        try:
            return datetime.strptime(text or "", fmt).date()
        except ValueError:
            continue
    return None


def _eps(c: dict[str, Any]) -> EpsReport:
    inter = c.get("interimFinancials") or {}
    rows = {r.get("metric"): r for r in inter.get("rows") or []}
    row: dict[str, Any] = next((rows[m] for m in EPS_METRICS if m in rows), {})
    multi = sorted(c.get("multiYearFinancials") or [], key=lambda r: r.get("year") or 0)
    return EpsReport(
        annual=_f(row.get("annual")),
        q1=_f(row.get("q1")),
        q2=_f(row.get("q2")),
        q3=_f(row.get("q3")),
        half_year=_f(row.get("half")),
        nine_months=_f(row.get("nine")),
        period_ends={k: str(v) for k, v in (inter.get("periodEnds") or {}).items() if v},
        last_audited_year=_f(multi[-1].get("epsBasic")) if multi else _f(c.get("eps")),
    )


def _txt(v: Any) -> str | None:
    s = str(v).strip() if v is not None else ""
    return None if s in ("", "N/A", "n/a") else s


def _holding_date(text: str | None) -> str | None:
    """ "Sep 30, 2026" and "Dec 31, 2025 (year ended)" -> ISO date."""
    if not text:
        return None
    try:
        return datetime.strptime(text.split("(")[0].strip(), "%b %d, %Y").date().isoformat()
    except ValueError:
        return None


def _info(c: dict[str, Any]) -> CompanyInfo:
    raw_sec, raw_loans = c.get("companySecretary"), c.get("loanStatus")
    sec: dict[str, Any] = raw_sec if isinstance(raw_sec, dict) else {}
    loans: dict[str, Any] = raw_loans if isinstance(raw_loans, dict) else {}
    lot = _f(c.get("marketLot"))
    return CompanyInfo(
        head_office=_txt(c.get("hq")),
        registered_office=_txt(c.get("registeredOffice")),
        factory_address=_txt(c.get("factoryAddress")),
        phone=_txt(c.get("phone")),
        fax=_txt(c.get("fax")),
        email=_txt(c.get("email")),
        website=_txt(c.get("website")),
        secretary_name=_txt(sec.get("name")),
        secretary_email=_txt(sec.get("email")),
        secretary_phone=_txt(sec.get("phone")) or _txt(sec.get("cell")),
        authorized_capital_mn=_f(c.get("authorizedCapital")),
        reserve_mn=_f(c.get("reserveWithoutOci")),
        short_term_loan_mn=_f(loans.get("shortTerm")),
        long_term_loan_mn=_f(loans.get("longTerm")),
        operational_status=_txt(c.get("operationalStatus")),
        agm_date=_txt(c.get("agmDate")),
        market_lot=int(lot) if lot else None,
    )


def _year_history(c: dict[str, Any]) -> tuple[YearFinancial, ...]:
    paid = {int(d["year"]): d for d in c.get("dividendHistory") or [] if d.get("year")}
    out = []
    for r in sorted(c.get("multiYearFinancials") or [], key=lambda x: x.get("year") or 0):
        if not r.get("year"):
            continue
        year = int(r["year"])
        out.append(
            YearFinancial(
                year=year,
                eps=_f(r.get("epsBasic")),
                nav=_f(r.get("nav")),
                profit_mn=_f(r.get("profit")),
                pe=_f(r.get("pe")),
                cash_dividend_pct=_f(r.get("dividendPct"))
                if r.get("dividendPct")
                else _f((paid.get(year) or {}).get("cash")),
                dividend_yield_pct=_f(r.get("dividendYield")),
            )
        )
    return tuple(out)


def _holding_history(c: dict[str, Any]) -> tuple[ShareholdingPattern, ...]:
    out = []
    for h in c.get("sharePattern") or []:
        p = h.get("pattern") or {}
        out.append(
            ShareholdingPattern(
                as_of=_holding_date(h.get("date")) or h.get("date"),
                sponsor_pct=_f(p.get("sponsor")),
                government_pct=_f(p.get("government")),
                institution_pct=_f(p.get("institution")),
                foreign_pct=_f(p.get("foreign")),
                public_pct=_f(p.get("public")),
            )
        )
    return tuple(out)


def parse_company_page(html: str, symbol: Symbol, fetched_at: datetime) -> CompanyPage:
    data = extract_flight(html)
    c = data.get("company")
    if not c or not c.get("code"):
        raise NotFoundError(f"{symbol} is not a DSE trading code", symbol=str(symbol))
    series = data.get("series")
    if not series:
        raise UpstreamUnavailableError(f"{symbol}: company page has no price series — page format changed")

    pattern = (c.get("sharePattern") or [{}])[-1]
    sp = pattern.get("pattern") or {}
    fundamentals = Fundamentals(
        eps=_eps(c),
        nav=_f(c.get("nav")) or _f(c.get("bookValue")),
        face_value=_f(c.get("faceValue")) or 10.0,
        paid_up_capital=_f(c.get("paidUpCapital")),
        market_cap=_f(c.get("marketCap")),
        free_float_pct=_f(c.get("freeFloat")),
        shareholding=ShareholdingPattern(
            as_of=pattern.get("date"),
            sponsor_pct=_f(sp.get("sponsor")),
            government_pct=_f(sp.get("government")),
            institution_pct=_f(sp.get("institution")),
            foreign_pct=_f(sp.get("foreign")),
            public_pct=_f(sp.get("public")),
        ),
        dividends=tuple(
            Dividend(int(d["year"]), _f(d.get("cash")) or 0.0, _f(d.get("stock")) or 0.0)
            for d in c.get("dividendHistory") or []
            if d.get("year")
        ),
        pe_dse=_f(c.get("pe")),
        pe_dse_trailing=_f(((c.get("peUnauditedTable") or {}).get("trailing") or [None])[-1]),
        dividend_yield_pct=_f(c.get("dividendYield")),
        week_high_52=_f(c.get("weekHigh52")),
        week_low_52=_f(c.get("weekLow52")),
        year_end=c.get("yearEnd"),
        listing_year=int(c["listingYear"]) if c.get("listingYear") else None,
        info=_info(c),
        year_history=_year_history(c),
        holding_history=_holding_history(c),
        schema=FUNDAMENTALS_SCHEMA,
    )
    instrument = Instrument(
        symbol=symbol,
        name=c.get("name") or str(symbol),
        sector=c.get("sector"),
        category=c.get("category"),
        board=c.get("board"),
        asset_type=None,
        isin=c.get("isin"),
    )
    bars = tuple(
        DailyBar(
            symbol,
            date.fromisoformat(b["date"]),
            _dec(b["open"]),
            _dec(b["high"]),
            _dec(b["low"]),
            _dec(b["price"]),
            int(b.get("volume") or 0),
            int(b["trades"]) if b.get("trades") is not None else None,
            BarSource.PAGE,
        )
        for b in series
    )
    news = tuple(
        Announcement(
            id=str(n["id"]),
            symbol=symbol,
            published_on=_day(n.get("date")),
            kind=n.get("type"),
            title=n.get("summary"),
            body=n.get("body") or "",
        )
        for n in c.get("recentAnnouncements") or []
        if n.get("id")
    )
    return CompanyPage(
        instrument=instrument,
        fundamentals=fundamentals,
        bars=bars,
        announcements=news,
        last_price=_f(c.get("price")),
        fetched_at=fetched_at,
    )


def parse_snapshot(obj: dict[str, Any]) -> MarketSnapshot:
    try:
        cols, rows = obj["prices"]["cols"], obj["prices"]["rows"]
    except (KeyError, TypeError) as e:
        raise UpstreamUnavailableError(f"snapshot shape changed: missing {e}") from e
    market = obj.get("market") or {}
    session = market.get("session") or obj["prices"].get("session") or {}
    quotes: dict[str, Quote] = {}
    for row in rows:
        q = dict(zip(cols, row, strict=False))
        try:
            sym = Symbol(str(q["code"]))
        except Exception:  # noqa: S112 — one malformed code must not drop the whole market
            continue
        quotes[sym.value] = Quote(
            symbol=sym,
            ltp=_f(q.get("ltp")),
            ycp=_f(q.get("ycp")),
            open=_f(q.get("open")),
            high=_f(q.get("high")),
            low=_f(q.get("low")),
            close=_f(q.get("close")) or None,
            volume=int(q.get("volume") or 0),
            value_mn=_f(q.get("value")),
            trades=int(q["trades"]) if q.get("trades") is not None else None,
            category=q.get("category"),
            sector=q.get("sector"),
            asset_type=q.get("assetType"),
        )
    return MarketSnapshot(
        session_date=_day(session.get("date")),
        is_open=bool(session.get("isOpen")),
        trading_day=bool(session.get("tradingDay")),
        trade_time=(market.get("totals") or {}).get("tradeTime"),
        quotes=quotes,
    )
