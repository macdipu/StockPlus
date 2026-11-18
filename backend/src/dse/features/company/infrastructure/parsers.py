"""Parse the three public sources into dossier parts. Pure functions; every shape assumption lives here.

stocknow   GET /api/v1/instruments/{SYM}/fundamentals/{k1,k2,…}?groupBy=meta_date,meta_key&yearLimit=10
           → {"2026-06-30": {"earning_per_share": [{"meta_value": "8.24", "meta_date": …}], …}, …}
           GET /api/v1/instruments/{SYM}/news → {"data": [{"date", "title", "details", …}], …}
amarstock  GET /stock/{SYM}: server-rendered HTML; the statements are <table>s whose header row is the
           years and whose last row is EPS (profit & loss), NAV (balance sheet) or NOCFPS (cash flow).
           Numbers use South-Asian grouping ("1,40,88,95,470"). Tags are often left unclosed.
topstock   GET /stock/{SYM}: Next.js page; JSON objects ("extFinancials", "financials", "rating",
           "declaration") sit inside the self.__next_f flight payload.
"""

import json
import re
from collections.abc import Mapping
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Any

from dse.features.company.domain.entities import (
    AmarStockPart,
    Capital,
    Contact,
    CreditRating,
    DirectorTrade,
    DividendRecord,
    Events,
    FinancialYear,
    NewsItem,
    PeriodValue,
    QuarterlyEps,
    Shareholding,
    Statement,
    StatementRow,
    StockNowPart,
    TopStockPart,
)

STOCKNOW_KEYS = (
    "earning_per_share",
    "q1_eps_cont_op",
    "q2_eps_cont_op",
    "q3_eps_cont_op",
    "half_year_eps_cont_op",
    "q3_nine_months_eps",
    "net_asset_val_per_share",
    "nocf_per_share",
    "cash_dividend",
    "stock_dividend",
    "share_percentage_director",
    "share_percentage_govt",
    "share_percentage_institute",
    "share_percentage_foreign",
    "share_percentage_public",
    "long_term_loan",
    "short_term_loan",
    "reserve_and_surp",
    "paid_up_capital",
    "authorized_capital",
    "total_no_securities",
    "record_date",
    "last_agm_held",
    "office_address",
    "phone_number",
    "fax_number",
    "email",
    "website",
    "listing_year",
    "operational_status",
    "year_end",
)
_QUARTERS = {
    "q1_eps_cont_op": "q1",
    "q2_eps_cont_op": "q2",
    "q3_eps_cont_op": "q3",
    "half_year_eps_cont_op": "h1",
    "q3_nine_months_eps": "9m",
}
MAX_NEWS = 15


def _num(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, int | float) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip().replace(",", "")
    if s in ("", "-", "—", "N/A", "n/a"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    try:
        f = float(s.strip("()"))
    except ValueError:
        return None
    return -f if neg else f


def _text(v: Any) -> str | None:
    s = str(v).strip() if v is not None else ""
    return s or None


# ============================================================================================ stocknow
def _by_key(payload: Mapping[str, Any]) -> dict[str, list[tuple[str, Any]]]:
    """{meta_key: [(meta_date, meta_value), …]} sorted by date, whatever the grouping shape."""
    out: dict[str, list[tuple[str, Any]]] = {}

    def add(row: Any) -> None:
        if isinstance(row, dict) and row.get("meta_key"):
            out.setdefault(str(row["meta_key"]), []).append(
                (str(row.get("meta_date") or ""), row.get("meta_value"))
            )

    for group in payload.values():
        if isinstance(group, dict):
            for rows in group.values():
                for row in rows if isinstance(rows, list) else [rows]:
                    add(row)
        elif isinstance(group, list):
            for row in group:
                add(row)
    for rows in out.values():
        rows.sort(key=lambda t: t[0])
    return out


def _series(rows: list[tuple[str, Any]]) -> tuple[PeriodValue, ...]:
    seen: dict[str, float] = {}
    for d, v in rows:
        f = _num(v)
        if f is not None and d and not d.startswith("0000"):
            seen[d] = f
    return tuple(PeriodValue(d, v) for d, v in sorted(seen.items()))


def _last(rows: list[tuple[str, Any]] | None) -> tuple[str | None, Any]:
    return rows[-1] if rows else (None, None)


def _iso_dmy(v: Any) -> str | None:
    s = _text(v)
    if not s:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return s


def parse_stocknow(payload: Mapping[str, Any], news: Mapping[str, Any] | None = None) -> StockNowPart:
    k = _by_key(payload)
    quarterly = tuple(
        sorted(
            (
                QuarterlyEps(pv.period_end, label, pv.value)
                for key, label in _QUARTERS.items()
                for pv in _series(k.get(key, []))
            ),
            key=lambda q: (q.period_end, q.period),
        )
    )
    cash = {pv.period_end: pv.value for pv in _series(k.get("cash_dividend", []))}
    stock = {pv.period_end: pv.value for pv in _series(k.get("stock_dividend", []))}
    dividends = tuple(
        DividendRecord(d, cash.get(d, 0.0), stock.get(d, 0.0)) for d in sorted(set(cash) | set(stock))
    )
    holders: dict[str, dict[str, float | None]] = {}
    for key, field in (
        ("share_percentage_director", "director"),
        ("share_percentage_govt", "government"),
        ("share_percentage_institute", "institute"),
        ("share_percentage_foreign", "foreign"),
        ("share_percentage_public", "public"),
    ):
        for pv in _series(k.get(key, [])):
            holders.setdefault(pv.period_end, {})[field] = pv.value
    shareholding = tuple(
        Shareholding(
            as_of=d,
            director=h.get("director"),
            government=h.get("government"),
            institute=h.get("institute"),
            foreign=h.get("foreign"),
            public=h.get("public"),
        )
        for d, h in sorted(holders.items())
    )
    loans_as_of, lt = _last(k.get("long_term_loan"))
    shares = _num(_last(k.get("total_no_securities"))[1])
    listing = _num(_last(k.get("listing_year"))[1])
    record = _last(k.get("record_date"))
    items = (news or {}).get("data") if isinstance(news, Mapping) else None
    return StockNowPart(
        contact=Contact(
            address=max(
                (t for _, v in k.get("office_address", []) if (t := _text(v))), key=len, default=None
            ),
            phone=_text(_last(k.get("phone_number"))[1]),
            fax=_text(_last(k.get("fax_number"))[1]),
            email=_text(_last(k.get("email"))[1]),
            website=_text(_last(k.get("website"))[1]),
        ),
        listing_year=int(listing) if listing else None,
        year_end=_text(_last(k.get("year_end"))[1]),
        operational_status=_text(_last(k.get("operational_status"))[1]),
        capital=Capital(
            authorized_mn=_num(_last(k.get("authorized_capital"))[1]),
            paid_up_mn=_num(_last(k.get("paid_up_capital"))[1]),
            reserve_mn=_num(_last(k.get("reserve_and_surp"))[1]),
            long_term_loan_mn=_num(lt),
            short_term_loan_mn=_num(_last(k.get("short_term_loan"))[1]),
            total_shares=int(shares) if shares else None,
            loans_as_of=loans_as_of,
        ),
        eps_annual=_series(k.get("earning_per_share", [])),
        eps_quarterly=quarterly,
        nav=_series(k.get("net_asset_val_per_share", [])),
        nocfps=_series(k.get("nocf_per_share", [])),
        dividends=dividends,
        shareholding=shareholding,
        events=Events(record_date=_iso_dmy(record[1]), last_agm=_iso_dmy(_last(k.get("last_agm_held"))[1])),
        news=tuple(_news(n) for n in (items or [])[:MAX_NEWS] if isinstance(n, dict)),
    )


def _news(n: Mapping[str, Any]) -> NewsItem:
    d = _text(n.get("date")) or (_text(n.get("post_date")) or "")[:10]
    try:
        day = date.fromisoformat(d) if d else None
    except ValueError:
        day = None
    body = _text(n.get("details")) or _text(n.get("summary_en")) or ""
    title = _text(n.get("title")) or (body.split(":")[0][:80] if body else "Announcement")
    return NewsItem(day=day, title=title, body=body)


# ============================================================================================ amarstock
class _Tables(HTMLParser):
    """Collect every <table> as rows of cell text. Tolerates unclosed <tr>/<td>/<th>."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self.bold: list[list[bool]] = []
        self._depth = 0
        self._cell: list[str] | None = None
        self._bold = False

    def _close_cell(self) -> None:
        if self._cell is not None and self.tables and self.tables[-1]:
            self.tables[-1][-1].append(" ".join("".join(self._cell).split()))
        self._cell = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._depth += 1
            self.tables.append([])
            self.bold.append([])
        elif self._depth and tag == "tr":
            self._close_cell()
            self.tables[-1].append([])
            self.bold[-1].append(False)
        elif self._depth and tag in ("td", "th"):
            self._close_cell()
            if not self.tables[-1]:
                self.tables[-1].append([])
                self.bold[-1].append(False)
            self._cell = []
            cls = dict(attrs).get("class") or ""
            if "font-weight-bold" in cls and not self.tables[-1][-1]:
                self.bold[-1][-1] = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th"):
            self._close_cell()
        elif tag == "table" and self._depth:
            self._close_cell()
            self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def html_tables(html: str) -> tuple[list[list[list[str]]], list[list[bool]]]:
    p = _Tables()
    p.feed(html)
    p.close()
    return p.tables, p.bold


_STATEMENT_KIND = (("NOCFPS", "cash_flow"), ("NAV", "balance_sheet"), ("EPS", "income"))
_YEAR = re.compile(r"^(19|20)\d{2}$")


def _dmy(s: str) -> date | None:
    try:
        return datetime.strptime(s.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def parse_amarstock(html: str) -> AmarStockPart:
    tables, bold = html_tables(html)
    statements: list[Statement] = []
    trades: list[DirectorTrade] = []
    seen_trades: set[tuple[Any, ...]] = set()
    for t, b in zip(tables, bold, strict=True):
        rows = [r for r in t if r]
        if len(rows) < 3:
            continue
        head = rows[0]
        years = [c for c in head[1:] if _YEAR.match(c)]
        if years and len(years) == len(head) - 1:
            last_label = rows[-1][0]
            kind = next((k for marker, k in _STATEMENT_KIND if marker in last_label), None)
            if kind and all(s.kind != kind for s in statements):
                body = []
                for r, is_bold in zip(t[1:], b[1:], strict=False):
                    if not r or not r[0]:
                        continue
                    vals = tuple(_num(x) for x in (r[1:] + [""] * len(years))[: len(years)])
                    body.append(StatementRow(label=r[0], values=vals, total=is_bold))
                statements.append(Statement(kind=kind, years=tuple(years), rows=tuple(body)))
            continue
        for r in rows:
            if len(r) >= 5 and _dmy(r[0]) and r[2] in ("Buy", "Sell", "Transfer", "Gift", "Inheritance"):
                key = tuple(r[:5])
                if key in seen_trades:  # the page repeats rows when an order was filled in parts
                    continue
                seen_trades.add(key)
                qty = _num(r[3])
                trades.append(
                    DirectorTrade(
                        day=_dmy(r[0]),
                        holder=r[1],
                        side=r[2],
                        quantity=int(qty) if qty is not None else None,
                        price=_num(r[4]),
                    )
                )
    order = {"income": 0, "balance_sheet": 1, "cash_flow": 2}
    statements.sort(key=lambda s: order[s.kind])
    return AmarStockPart(statements=tuple(statements), director_trades=tuple(trades))


# ============================================================================================ topstock
_FLIGHT_PUSH = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)\s*</script>', re.S)


def flight_objects(html: str, keys: tuple[str, ...]) -> dict[str, Any]:
    chunks = _FLIGHT_PUSH.findall(html)
    text = "".join(json.loads(f'"{c}"') for c in chunks)
    dec = json.JSONDecoder()
    out: dict[str, Any] = {}
    for key in keys:
        m = re.search(rf'"{key}":\s*([\[{{])', text)
        if m:
            try:
                out[key], _ = dec.raw_decode(text, m.start(1))
            except json.JSONDecodeError:
                continue
    return out


def parse_topstock(html: str) -> TopStockPart:
    o = flight_objects(html, ("extFinancials", "financials", "rating", "declaration"))
    by_year: dict[int, dict[str, Any]] = {}
    for r in o.get("financials") or []:
        if isinstance(r, dict) and r.get("year"):
            by_year.setdefault(int(r["year"]), {}).update(
                eps=_num(r.get("eps")),
                nav_per_share=_num(r.get("nav_per_share")),
                dividend_cash_pct=_num(r.get("cash_dividend_pct")),
                net_profit=(_num(r.get("profit_mn")) or 0) * 1e6 if r.get("profit_mn") is not None else None,
            )
    for r in o.get("extFinancials") or []:
        if isinstance(r, dict) and r.get("year"):
            y = by_year.setdefault(int(r["year"]), {})
            for src, dst in (
                ("revenue", "revenue"),
                ("gross_profit", "gross_profit"),
                ("net_profit", "net_profit"),
                ("operating_cf", "operating_cf"),
                ("investing_cf", "investing_cf"),
                ("total_assets", "total_assets"),
                ("total_equity", "total_equity"),
                ("total_debt", "total_debt"),
                ("cash_and_equivalents", "cash"),
                ("interest_expense", "interest_expense"),
                ("nocfps", "nocfps"),
            ):
                v = _num(r.get(src))
                if v is not None:
                    y[dst] = v
    years = tuple(FinancialYear(year=yr, **vals) for yr, vals in sorted(by_year.items()))
    rt = o.get("rating")
    rating = (
        CreditRating(
            agency=_text(rt.get("agency")),
            long_term=_text(rt.get("long_term")),
            short_term=_text(rt.get("short_term")),
            outlook=_text(rt.get("outlook")),
            rated_on=_text(rt.get("date")),
        )
        if isinstance(rt, dict) and (rt.get("long_term") or rt.get("short_term"))
        else None
    )
    raw_dc = o.get("declaration")
    dc: dict[str, Any] = raw_dc if isinstance(raw_dc, dict) else {}
    return TopStockPart(
        years=years,
        rating=rating,
        events=Events(
            record_date=(_text(dc.get("record_date")) or "")[:10] or None,
            declaration_date=(_text(dc.get("declaration_date")) or "")[:10] or None,
            declared_dividend_pct=_num(dc.get("dividend_pct")),
            declared_dividend_type=_text(dc.get("dividend_type")),
        ),
    )
