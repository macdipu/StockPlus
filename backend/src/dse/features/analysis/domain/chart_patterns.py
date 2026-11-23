"""Chart patterns found from swing highs and lows: double top/bottom, head and shoulders (and inverse),
triangles, channels, wedges and ranges.

These are rule-based and approximate: a pattern is a *possible* shape, not a signal. Everything here is pure
(numpy in, dataclasses out) so it is tested on hand-built price paths.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

import numpy as np
import numpy.typing as npt

Direction = Literal["bullish", "bearish", "neutral"]
Status = Literal["forming", "confirmed"]
Floats = npt.NDArray[np.float64]

PIVOT_WINDOW = 3  # a swing high/low is the extreme of this many bars either side
MIN_SWING = 0.03  # moves smaller than 3% between swings are noise
LOOKBACK = 120  # bars considered
RECENT = 30  # a pattern must have ended this recently to be worth showing
MAX_SHOWN = 3  # a chart with more shapes than this stops being readable
PEAK_TOLERANCE = 0.025  # two tops (or bottoms) within 2.5% count as level
SHOULDER_TOLERANCE = 0.05
MIN_DEPTH = 0.03  # the trough between two tops is at least 3% below them
FIT_TOLERANCE = 0.02  # a pivot within 2% of a trendline "touches" it
FLAT = 0.0004  # a trendline moving less than 0.04% per bar is flat


@dataclass(frozen=True, slots=True)
class Pivot:
    i: int
    price: float
    kind: Literal["high", "low"]


@dataclass(frozen=True, slots=True)
class Point:
    day: date
    price: float
    label: str = ""


@dataclass(frozen=True, slots=True)
class Line:
    role: str  # "neckline", "upper", "lower"
    a: Point
    b: Point


@dataclass(frozen=True, slots=True)
class ChartPattern:
    kind: str
    name: str
    direction: Direction
    status: Status
    confidence: int  # 0-100: how cleanly the bars fit the shape, not a probability of success
    start: date
    end: date
    points: tuple[Point, ...]
    lines: tuple[Line, ...]
    summary: str


# ---------------------------------------------------------------------------------- pivots
def find_pivots(
    high: Floats, low: Floats, k: int = PIVOT_WINDOW, min_swing: float = MIN_SWING
) -> list[Pivot]:
    """Alternating swing highs and lows. Equal extremes keep the leftmost; small swings are skipped."""
    n = len(high)
    raw: list[Pivot] = []
    for i in range(k, n - k):
        if int(np.argmax(high[i - k : i + k + 1])) == k:
            raw.append(Pivot(i, float(high[i]), "high"))
        if int(np.argmin(low[i - k : i + k + 1])) == k:
            raw.append(Pivot(i, float(low[i]), "low"))
    raw.sort(key=lambda p: (p.i, p.kind))
    out: list[Pivot] = []
    for p in raw:
        if not out:
            out.append(p)
            continue
        last = out[-1]
        if p.kind == last.kind:  # two highs in a row: keep the higher (two lows: the lower)
            better = p.price > last.price if p.kind == "high" else p.price < last.price
            if better:
                out[-1] = p
        elif abs(p.price / last.price - 1) >= min_swing:
            out.append(p)
    return out


def _near(a: float, b: float, tol: float) -> bool:
    return abs(a / b - 1) <= tol if b else False


# ---------------------------------------------------------------------------------- reversals
def _double(days: list[date], close: Floats, piv: list[Pivot], top: bool) -> list[ChartPattern]:
    kind: Literal["high", "low"] = "high" if top else "low"
    out: list[ChartPattern] = []
    for j in range(len(piv) - 2):
        p1, mid, p2 = piv[j], piv[j + 1], piv[j + 2]
        if p1.kind != kind or p2.kind != kind or mid.kind == kind:
            continue
        if not _near(p1.price, p2.price, PEAK_TOLERANCE) or not 8 <= p2.i - p1.i <= 70:
            continue
        depth = (p1.price - mid.price) / p1.price if top else (mid.price - p1.price) / p1.price
        if depth < MIN_DEPTH:
            continue
        last = float(close[-1])
        broken = last < mid.price if top else last > mid.price
        failed = last > max(p1.price, p2.price) * 1.01 if top else last < min(p1.price, p2.price) * 0.99
        if failed:
            continue
        sym = 1 - abs(p1.price / p2.price - 1) / PEAK_TOLERANCE
        confidence = round(45 + 25 * sym + min(15, depth * 150) + (10 if broken else 0))
        name = "Double top" if top else "Double bottom"
        target = mid.price - (p1.price - mid.price) if top else mid.price + (mid.price - p1.price)
        out.append(
            ChartPattern(
                kind="double_top" if top else "double_bottom",
                name=name,
                direction="bearish" if top else "bullish",
                status="confirmed" if broken else "forming",
                confidence=min(95, confidence),
                start=days[p1.i],
                end=days[p2.i],
                points=(
                    Point(days[p1.i], p1.price, "1"),
                    Point(days[mid.i], mid.price),
                    Point(days[p2.i], p2.price, "2"),
                ),
                lines=(
                    Line(
                        "neckline",
                        Point(days[p1.i], mid.price),
                        Point(days[-1], mid.price),
                    ),
                ),
                summary=(
                    f"{name}: two {'peaks' if top else 'troughs'} near {p1.price:.2f} with the neckline at "
                    f"{mid.price:.2f}. "
                    + (
                        f"The close is {'below' if top else 'above'} the neckline; "
                        f"the measured move points to {target:.2f}."
                        if broken
                        else f"Confirmed only by a close {'below' if top else 'above'} {mid.price:.2f}."
                    )
                ),
            )
        )
    return out


def _head_shoulders(days: list[date], close: Floats, piv: list[Pivot], top: bool) -> list[ChartPattern]:
    kind: Literal["high", "low"] = "high" if top else "low"
    out: list[ChartPattern] = []
    for j in range(len(piv) - 4):
        ls, t1, head, t2, rs = piv[j : j + 5]
        if not (ls.kind == head.kind == rs.kind == kind and t1.kind == t2.kind != kind):
            continue
        if top:
            prominent = head.price > ls.price * 1.03 and head.price > rs.price * 1.03
        else:
            prominent = head.price < ls.price * 0.97 and head.price < rs.price * 0.97
        if not prominent or not _near(ls.price, rs.price, SHOULDER_TOLERANCE):
            continue
        if not (_near(t1.price, t2.price, 0.06) and rs.i - ls.i <= 110):
            continue
        slope = (t2.price - t1.price) / (t2.i - t1.i)

        def neck_at(i: int, t1: Pivot = t1, slope: float = slope) -> float:
            return t1.price + slope * (i - t1.i)

        last_i = len(close) - 1
        broken = float(close[-1]) < neck_at(last_i) if top else float(close[-1]) > neck_at(last_i)
        failed = float(close[-1]) > head.price if top else float(close[-1]) < head.price
        if failed:
            continue
        sym = 1 - abs(ls.price / rs.price - 1) / SHOULDER_TOLERANCE
        confidence = min(95, round(50 + 25 * sym + (15 if broken else 0)))
        name = "Head and shoulders" if top else "Inverse head and shoulders"
        height = abs(head.price - neck_at(head.i))
        target = neck_at(last_i) - height if top else neck_at(last_i) + height
        out.append(
            ChartPattern(
                kind="head_shoulders" if top else "inverse_head_shoulders",
                name=name,
                direction="bearish" if top else "bullish",
                status="confirmed" if broken else "forming",
                confidence=confidence,
                start=days[ls.i],
                end=days[rs.i],
                points=(
                    Point(days[ls.i], ls.price, "L"),
                    Point(days[head.i], head.price, "H"),
                    Point(days[rs.i], rs.price, "R"),
                ),
                lines=(
                    Line(
                        "neckline",
                        Point(days[t1.i], t1.price),
                        Point(days[last_i], float(neck_at(last_i))),
                    ),
                ),
                summary=(
                    f"{name}: head near {head.price:.2f} between shoulders near {ls.price:.2f} and "
                    f"{rs.price:.2f}. "
                    + (
                        f"The close is through the neckline; the measured move points to {target:.2f}."
                        if broken
                        else "Confirmed only by a close through the neckline."
                    )
                ),
            )
        )
    return out


# ---------------------------------------------------------------------------------- trendline shapes
def _fit(xs: list[int], ys: list[float]) -> tuple[float, float]:
    slope, intercept = np.polyfit(np.array(xs, dtype=float), np.array(ys, dtype=float), 1)
    return float(slope), float(intercept)


def _touches(xs: list[int], ys: list[float], slope: float, intercept: float) -> int:
    return sum(
        1 for x, y in zip(xs, ys, strict=True) if abs(y / (slope * x + intercept) - 1) <= FIT_TOLERANCE
    )


def _converging_shape(days: list[date], close: Floats, piv: list[Pivot]) -> list[ChartPattern]:
    n = len(close)
    window = [p for p in piv if p.i >= n - LOOKBACK]
    hi = [p for p in window if p.kind == "high"]
    lo = [p for p in window if p.kind == "low"]
    out: list[ChartPattern] = []
    # use the latest 3 or 4 pivots of each kind: the shape that is on the chart now
    for count in (4, 3):
        h, low_p = hi[-count:], lo[-count:]
        if len(h) < count or len(low_p) < count:
            continue
        hx, hy = [p.i for p in h], [p.price for p in h]
        lx, ly = [p.i for p in low_p], [p.price for p in low_p]
        start, end = min(hx[0], lx[0]), max(hx[-1], lx[-1])
        if end - start < 25 or end < n - RECENT:
            continue
        sh, ih = _fit(hx, hy)
        sl, il = _fit(lx, ly)
        if _touches(hx, hy, sh, ih) < count or _touches(lx, ly, sl, il) < count:
            continue
        mean = float(np.mean(hy + ly))
        rh, rl = sh / mean, sl / mean  # slopes as a share of price per bar
        upper_end, lower_end = sh * (n - 1) + ih, sl * (n - 1) + il
        upper_start, lower_start = sh * start + ih, sl * start + il
        if lower_end >= upper_end:  # the lines have already crossed
            continue
        last = float(close[-1])
        above, below = last > upper_end * 1.005, last < lower_end * 0.995
        if last > upper_end * 1.04 or last < lower_end * 0.96:
            continue  # broke out long ago
        gap_start, gap_end = upper_start - lower_start, upper_end - lower_end
        converging = gap_end < gap_start * 0.75
        parallel = abs(rh - rl) < 0.0006
        kind: str
        name: str
        direction: Direction
        if abs(rh) < FLAT and abs(rl) < FLAT:
            kind, name, direction = "range", "Trading range", "neutral"
        elif abs(rh) < FLAT and rl > FLAT and converging:
            kind, name, direction = "ascending_triangle", "Ascending triangle", "bullish"
        elif abs(rl) < FLAT and rh < -FLAT and converging:
            kind, name, direction = "descending_triangle", "Descending triangle", "bearish"
        elif rh < -FLAT and rl > FLAT and converging:
            kind, name, direction = "symmetrical_triangle", "Symmetrical triangle", "neutral"
        elif rh > FLAT and rl > FLAT and converging:
            kind, name, direction = "rising_wedge", "Rising wedge", "bearish"
        elif rh < -FLAT and rl < -FLAT and converging:
            kind, name, direction = "falling_wedge", "Falling wedge", "bullish"
        elif parallel and rh > FLAT:
            kind, name, direction = "rising_channel", "Rising channel", "bullish"
        elif parallel and rh < -FLAT:
            kind, name, direction = "falling_channel", "Falling channel", "bearish"
        else:
            continue
        status: Status = "confirmed" if above or below else "forming"
        touches = len(h) + len(low_p)
        confidence = min(95, 40 + 8 * touches + (10 if status == "confirmed" else 0))
        where = "above" if above else "below" if below else "inside"
        out.append(
            ChartPattern(
                kind=kind,
                name=name,
                direction=direction,
                status=status,
                confidence=confidence,
                start=days[start],
                end=days[-1],
                points=tuple(Point(days[p.i], p.price) for p in sorted(h + low_p, key=lambda q: q.i)),
                lines=(
                    Line(
                        "upper", Point(days[start], float(sh * start + ih)), Point(days[-1], float(upper_end))
                    ),
                    Line(
                        "lower", Point(days[start], float(sl * start + il)), Point(days[-1], float(lower_end))
                    ),
                ),
                summary=(
                    f"{name}: price is {where} the pattern between {lower_end:.2f} and {upper_end:.2f} "
                    f"({touches} touches). "
                    + (
                        "A close outside the lines is the signal."
                        if status == "forming"
                        else "It has broken out."
                    )
                ),
            )
        )
        break  # the longer fit wins; do not also report its 3-pivot subset
    return out


# ---------------------------------------------------------------------------------- entry point
def detect(days: list[date], high: Floats, low: Floats, close: Floats) -> list[ChartPattern]:
    """Chart patterns on the latest bars, newest first. The four arrays must be the same length."""
    n = len(close)
    if n < 40 or not (len(days) == len(high) == len(low) == n):
        return []
    lo_i = max(0, n - LOOKBACK)
    offset = lo_i
    h, lw, cl = high[lo_i:], low[lo_i:], close[lo_i:]
    d = days[lo_i:]
    piv = find_pivots(h, lw)
    found = (
        _double(d, cl, piv, True)
        + _double(d, cl, piv, False)
        + _head_shoulders(d, cl, piv, True)
        + _head_shoulders(d, cl, piv, False)
        + _converging_shape(d, cl, piv)
    )
    recent = [p for p in found if (d.index(p.end) + offset) >= n - RECENT]
    return _best(recent)[:MAX_SHOWN]


def _best(found: list[ChartPattern]) -> list[ChartPattern]:
    """Newest first; of two patterns of the same kind that overlap in time, only the more confident one."""
    kept: list[ChartPattern] = []
    for p in sorted(found, key=lambda q: (q.confidence, q.end), reverse=True):
        if not any(k.kind == p.kind and k.start <= p.end and p.start <= k.end for k in kept):
            kept.append(p)
    kept.sort(key=lambda q: (q.end, q.confidence), reverse=True)
    return kept
