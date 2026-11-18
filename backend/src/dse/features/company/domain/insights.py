"""Ratios and plain-language flags derived from a dossier. Pure functions.

Every ratio says what it was computed from, so a reader (or an AI agent) can check it.
"""

from dataclasses import dataclass

from dse.features.company.domain.entities import CompanyDossier, FinancialYear, PeriodValue, Shareholding

FACE_VALUE = 10.0


@dataclass(frozen=True, slots=True)
class Ratio:
    key: str
    label: str
    value: float | None
    unit: str  # % | x | Tk
    basis: str


@dataclass(frozen=True, slots=True)
class Flag:
    tone: str  # good | warn | bad
    text: str


def _latest(vals: tuple[PeriodValue, ...], n: int = 1) -> list[PeriodValue]:
    return sorted(vals, key=lambda v: v.period_end)[-n:]


def _pct(a: float | None, b: float | None) -> float | None:
    return a / b * 100 if a is not None and b not in (None, 0) else None


def _latest_year(d: CompanyDossier) -> FinancialYear | None:
    ys = [y for y in d.topstock.years if y.net_profit is not None]
    return max(ys, key=lambda y: y.year) if ys else None


def _holding_change(sh: tuple[Shareholding, ...], months: int) -> tuple[float | None, str | None]:
    rows = sorted((s for s in sh if s.director is not None), key=lambda s: s.as_of)
    if len(rows) < 2:
        return None, None
    last = rows[-1]
    past = rows[max(0, len(rows) - 1 - months)]
    if last.director is None or past.director is None:
        return None, None
    return last.director - past.director, past.as_of


def ratios(d: CompanyDossier, price: float | None) -> list[Ratio]:
    sn = d.exchange
    out: list[Ratio] = []
    fy = _latest_year(d)
    if fy:
        out.append(
            Ratio(
                "roe",
                "Return on equity",
                _pct(fy.net_profit, fy.total_equity),
                "%",
                f"net profit / equity, FY{fy.year}",
            )
        )
        out.append(
            Ratio(
                "net_margin",
                "Net profit margin",
                _pct(fy.net_profit, fy.revenue),
                "%",
                f"net profit / revenue, FY{fy.year}",
            )
        )
        out.append(
            Ratio(
                "gross_margin",
                "Gross margin",
                _pct(fy.gross_profit, fy.revenue),
                "%",
                f"gross profit / revenue, FY{fy.year}",
            )
        )
        de = fy.total_debt / fy.total_equity if fy.total_debt is not None and fy.total_equity else None
        out.append(Ratio("debt_to_equity", "Debt to equity", de, "x", f"total debt / equity, FY{fy.year}"))
    cap = sn.capital
    equity_mn = (cap.paid_up_mn or 0) + (cap.reserve_mn or 0)
    if cap.total_loan_mn is not None and equity_mn > 0:
        out.append(
            Ratio(
                "loan_to_equity",
                "Loans to paid-up + reserve",
                cap.total_loan_mn / equity_mn,
                "x",
                f"(short + long-term loans) / (paid-up + reserve), loans as of {cap.loans_as_of or '?'}",
            )
        )
    eps = _latest(sn.eps_annual, 4)
    if len(eps) >= 2 and eps[-2].value > 0:
        out.append(
            Ratio(
                "eps_growth",
                "EPS growth (last year)",
                (eps[-1].value / eps[-2].value - 1) * 100,
                "%",
                f"annual EPS {eps[-2].value} ({eps[-2].period_end[:4]}) → {eps[-1].value} "
                f"({eps[-1].period_end[:4]})",
            )
        )
    if len(eps) >= 4 and eps[0].value > 0 and eps[-1].value > 0:
        years = len(eps) - 1
        out.append(
            Ratio(
                "eps_cagr",
                f"EPS growth per year ({years}y)",
                ((eps[-1].value / eps[0].value) ** (1 / years) - 1) * 100,
                "%",
                f"compound growth of annual EPS {eps[0].period_end[:4]}-{eps[-1].period_end[:4]}",
            )
        )
    nocf = _latest(sn.nocfps)
    if not nocf:  # the exchange does not publish cash flow per share; TopStock's yearly figures do
        with_cash = [y for y in d.topstock.years if y.nocfps is not None]
        same_year = [y for y in with_cash if eps and str(y.year) == eps[-1].period_end[:4]]
        pick = same_year[-1] if same_year else (max(with_cash, key=lambda y: y.year) if with_cash else None)
        nocf = [PeriodValue(str(pick.year), float(pick.nocfps))] if pick and pick.nocfps is not None else []
    if eps and nocf and eps[-1].value > 0:
        out.append(
            Ratio(
                "cash_backing",
                "Operating cash per Tk of profit",
                nocf[-1].value / eps[-1].value,
                "x",
                f"NOCF per share {nocf[-1].value} / EPS {eps[-1].value}",
            )
        )
    divs = sorted(sn.dividends, key=lambda x: x.period_end)
    if divs and eps and eps[-1].value > 0:
        dps = divs[-1].cash_pct / 100 * FACE_VALUE
        out.append(
            Ratio(
                "payout",
                "Dividend payout",
                dps / eps[-1].value * 100,
                "%",
                f"cash dividend Tk {dps:.2f} / EPS {eps[-1].value}",
            )
        )
        if price:
            out.append(
                Ratio(
                    "dividend_yield",
                    "Dividend yield",
                    dps / price * 100,
                    "%",
                    f"last cash dividend Tk {dps:.2f} / price {price}",
                )
            )
    navs = _latest(sn.nav)
    if price and navs and navs[-1].value > 0:
        out.append(Ratio("pb", "Price / book", price / navs[-1].value, "x", f"price / NAV {navs[-1].value}"))
    return out


def flags(d: CompanyDossier, price: float | None) -> list[Flag]:
    r = {x.key: x.value for x in ratios(d, price)}
    out: list[Flag] = []
    roe = r.get("roe")
    if roe is not None:
        out.append(
            Flag("good", f"Return on equity {roe:.1f}%: the business earns well on its capital.")
            if roe >= 15
            else Flag("warn", f"Return on equity only {roe:.1f}%.")
            if roe < 8
            else Flag("good", f"Return on equity {roe:.1f}%, reasonable.")
        )
    cb = r.get("cash_backing")
    if cb is not None:
        if cb >= 0.8:
            out.append(Flag("good", f"Profit is backed by cash: operating cash is {cb:.1f}x the EPS."))
        elif cb < 0:
            out.append(Flag("bad", "Operating cash flow is negative while the company reports a profit."))
        else:
            out.append(Flag("warn", f"Operating cash covers only {cb:.1f}x of the reported profit."))
    # the sources count debt differently (some only long-term); judge on the larger, more cautious figure
    gearing = [x for x in (r.get("debt_to_equity"), r.get("loan_to_equity")) if x is not None]
    de = max(gearing) if gearing else None
    if de is not None:
        if de >= 1.5:
            out.append(Flag("bad", f"Heavy borrowing: debt is {de:.1f}x equity."))
        elif de >= 0.8:
            out.append(Flag("warn", f"Moderate borrowing: debt is {de:.1f}x equity."))
        else:
            out.append(Flag("good", f"Low borrowing: debt is {de:.1f}x equity."))
    g = r.get("eps_growth")
    if g is not None:
        out.append(
            Flag(
                "good" if g > 0 else "warn",
                f"Annual EPS {'grew' if g > 0 else 'fell'} {abs(g):.0f}% last year.",
            )
        )
    paid = [x for x in d.exchange.dividends if x.cash_pct > 0 or x.stock_pct > 0]
    recent = sorted(d.exchange.dividends, key=lambda x: x.period_end)[-5:]
    if recent:
        n = sum(1 for x in recent if x.cash_pct > 0)
        out.append(
            Flag(
                "good" if n >= 4 else "warn", f"Paid a cash dividend in {n} of the last {len(recent)} years."
            )
        )
    elif not paid:
        out.append(Flag("warn", "No dividend history found."))
    change, since = _holding_change(d.exchange.shareholding, 6)
    if change is not None and abs(change) >= 0.5:
        out.append(
            Flag(
                "good" if change > 0 else "warn",
                f"Sponsors/directors {'raised' if change > 0 else 'cut'} their holding by "
                f"{abs(change):.2f} points since {since}.",
            )
        )
    sh = sorted(d.exchange.shareholding, key=lambda s: s.as_of)
    if sh and sh[-1].director is not None and sh[-1].director < 30:
        out.append(
            Flag("warn", f"Sponsors/directors hold only {sh[-1].director:.1f}% (DSE rule: at least 30%).")
        )
    rt = d.topstock.rating
    if rt is not None and rt.long_term:
        out.append(
            Flag(
                "good" if (rt.long_term or "").startswith(("AAA", "AA")) else "warn",
                f"Credit rating {rt.long_term} ({rt.agency or 'agency ?'}, {rt.outlook or 'no outlook'}, "
                f"{rt.rated_on or 'date ?'}).",
            )
        )
    return out
