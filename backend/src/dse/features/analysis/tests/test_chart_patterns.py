"""Chart patterns on hand-built price paths whose shape is known."""

from collections.abc import Sequence
from datetime import date, timedelta
from itertools import pairwise

import numpy as np

from dse.features.analysis.domain.chart_patterns import detect, find_pivots


def path(vertices: Sequence[tuple[int, float]]) -> tuple[list[date], np.ndarray, np.ndarray, np.ndarray]:
    """A price path through the given (bar, price) vertices, with a thin high/low band around each close."""
    xs, ys = zip(*vertices, strict=True)
    close = np.interp(np.arange(xs[-1] + 1), xs, ys).astype(float)
    start = date(2026, 1, 1)
    days = [start + timedelta(days=i) for i in range(len(close))]
    return days, close * 1.002, close * 0.998, close


def names(vertices: Sequence[tuple[int, float]]) -> dict[str, str]:
    days, hi, lo, cl = path(vertices)
    return {p.kind: p.status for p in detect(days, hi, lo, cl)}


def test_pivots_alternate_and_skip_small_swings() -> None:
    _, hi, lo, _ = path([(0, 100), (10, 110), (20, 100), (22, 100.5), (30, 112), (40, 100)])
    piv = find_pivots(hi, lo)
    assert [p.kind for p in piv] == ["high", "low", "high", "low"][: len(piv)]
    assert all(a.kind != b.kind for a, b in pairwise(piv))


def test_double_top_confirmed_when_the_close_breaks_the_neckline() -> None:
    assert names([(0, 80), (20, 100), (35, 88), (50, 99), (60, 86)]) == {"double_top": "confirmed"}


def test_double_top_still_forming_above_the_neckline() -> None:
    assert names([(0, 80), (20, 100), (35, 88), (50, 99), (58, 95)]) == {"double_top": "forming"}


def test_double_bottom() -> None:
    assert names([(0, 120), (20, 100), (35, 112), (50, 101), (60, 108)]) == {"double_bottom": "forming"}


def test_head_and_shoulders_with_neckline_break() -> None:
    found = names([(0, 80), (15, 100), (25, 90), (40, 115), (55, 90), (70, 100), (80, 85)])
    assert found.get("head_shoulders") == "confirmed"


def test_inverse_head_and_shoulders() -> None:
    found = names([(0, 120), (15, 100), (25, 110), (40, 85), (55, 110), (70, 100), (80, 115)])
    assert found.get("inverse_head_shoulders") == "confirmed"


def test_ascending_triangle() -> None:
    v = [(0, 90), (10, 100), (20, 80), (30, 100), (40, 86), (50, 100), (60, 92), (70, 100), (80, 99)]
    days, hi, lo, cl = path(v)
    [p] = [x for x in detect(days, hi, lo, cl) if x.kind == "ascending_triangle"]
    assert p.direction == "bullish"
    assert p.status == "forming"
    assert {line.role for line in p.lines} == {"upper", "lower"}
    assert p.lines[0].b.day == days[-1]  # the lines run to the latest bar


def test_a_steady_trend_has_no_pattern() -> None:
    assert names([(0, 100), (100, 200)]) == {}


def test_too_little_history_gives_nothing() -> None:
    days, hi, lo, cl = path([(0, 100), (10, 110), (20, 100)])
    assert detect(days, hi, lo, cl) == []


def test_an_old_pattern_is_not_reported() -> None:
    # a double top that ended 60+ bars ago, followed by a long flat stretch
    v = [(0, 80), (20, 100), (35, 88), (50, 99), (60, 86), (150, 86)]
    assert "double_top" not in names(v)


def test_a_triangle_that_dips_below_its_support_is_marked_confirmed() -> None:
    v = [(0, 90), (10, 100), (20, 80), (30, 100), (40, 86), (50, 100), (60, 92), (70, 100), (80, 95)]
    days, hi, lo, cl = path(v)
    [p] = [x for x in detect(days, hi, lo, cl) if x.kind == "ascending_triangle"]
    assert p.status == "confirmed"


def test_at_most_three_patterns_and_no_overlapping_duplicates() -> None:
    # a long zig-zag of equal tops and bottoms yields many double tops/bottoms; only a few survive
    v = [(0, 100)] + [(i * 12, 100 if i % 2 == 0 else 90) for i in range(1, 12)]
    days, hi, lo, cl = path(v)
    found = detect(days, hi, lo, cl)
    assert len(found) <= 3
    tops = [p for p in found if p.kind == "double_top"]
    assert all(not (a.start <= b.end and b.start <= a.end) for a in tops for b in tops if a is not b)
