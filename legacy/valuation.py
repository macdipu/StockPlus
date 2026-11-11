"""Fair-value methods. Every row carries its inputs so the reader can check the maths."""
from __future__ import annotations

import math

import config as C


def gap_pct(fair: float | None, price: float) -> float | None:
    """+ means the fair value is above the market price (upside)."""
    return None if fair is None or not price else (fair / price - 1) * 100


def graham_number(eps: float, nav: float) -> float | None:
    return math.sqrt(22.5 * eps * nav) if eps > 0 and nav > 0 else None


def ddm(dps: float, r: float, g: float) -> float | None:
    """Gordon growth: D1 / (r - g), D1 = D0 * (1 + g)."""
    return dps * (1 + g) / (r - g) if dps > 0 and r > g else None


def dcf_two_stage(eps: float, g1: float, g2: float, r: float, years: int = C.DCF_YEARS) -> float | None:
    """EPS grows at g1 for `years`, then at g2 forever; everything discounted at r."""
    if eps <= 0 or r <= g2:
        return None
    pv, e = 0.0, eps
    for t in range(1, years + 1):
        e *= 1 + g1
        pv += e / (1 + r) ** t
    terminal = e * (1 + g2) / (r - g2)
    return pv + terminal / (1 + r) ** years


def reverse_dcf(price: float, eps: float, g2: float, r: float, years: int = C.DCF_YEARS,
                lo: float = -0.9, hi: float = 2.0) -> float | None:
    """Stage-1 growth that makes the two-stage DCF equal the market price (bisection)."""
    if eps <= 0 or price <= 0 or r <= g2:
        return None
    f = lambda g: dcf_two_stage(eps, g, g2, r, years) - price
    if f(lo) > 0 or f(hi) < 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def value(fund: dict) -> dict:
    price, eps, nav, dps = fund.get("ltp"), fund.get("eps_ttm"), fund.get("nav"), fund.get("dps")
    rows, notes = [], []

    def add(method, inputs, fair):
        rows.append({"method": method, "inputs": inputs, "fair_value": fair, "gap_pct": gap_pct(fair, price)})

    eps_ok = eps is not None and eps > 0
    if not eps_ok:
        notes.append(f"EPS is {eps if eps is not None else 'missing'} — P/E, Graham, DCF and reverse DCF skipped.")
    else:
        for m in C.PE_MULTIPLES:
            add(f"P/E {m}x", f"TTM EPS {eps:.2f} ({fund.get('eps_ttm_basis')}) × {m}", eps * m)

    if nav and nav > 0:
        for m in C.PB_MULTIPLES:
            add(f"P/B {m}x", f"NAV/share {nav:.2f} × {m}", nav * m)
    else:
        notes.append("NAV missing or not positive — P/B skipped.")

    if eps_ok and nav and nav > 0:
        add("Graham Number", f"√(22.5 × EPS {eps:.2f} × NAV {nav:.2f})", graham_number(eps, nav))

    r, g = C.DDM_REQUIRED_RETURN, C.DDM_GROWTH
    if dps and dps > 0:
        add("Dividend discount", f"D0 {dps:.2f} × (1+{g:.0%}) / ({r:.0%} − {g:.0%})", ddm(dps, r, g))
    else:
        notes.append("No cash dividend — DDM skipped.")

    if eps_ok:
        for case, p in C.DCF_CASES.items():
            add(f"DCF ({case})",
                f"EPS {eps:.2f}, {C.DCF_YEARS}y @ {p['g1']:.0%}, then {p['g2']:.0%}, discount {p['r']:.0%}",
                dcf_two_stage(eps, p["g1"], p["g2"], p["r"]))

    implied = None
    if eps_ok and price:
        b = C.DCF_CASES["base"]
        implied = reverse_dcf(price, eps, b["g2"], b["r"])
        txt = (f"price {price:.2f} implies {implied:.1%} EPS growth/yr for {C.DCF_YEARS}y "
               f"(then {b['g2']:.0%}, discount {b['r']:.0%})" if implied is not None
               else "no growth rate in [-90%, 200%] reproduces the price")
        notes.append("Reverse DCF: " + txt)

    fairs = [x["fair_value"] for x in rows if x["fair_value"]]
    return {"price": price, "rows": rows, "notes": notes, "implied_growth": implied,
            "median_fair_value": sorted(fairs)[len(fairs) // 2] if fairs else None}
