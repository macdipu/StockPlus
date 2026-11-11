"""Return calculator, correlation and intraday bars: the domain maths and the use cases on a fake history."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from dse.core.clock import DHAKA
from dse.features.analysis.application.inputs import MinuteInput
from dse.features.analysis.application.use_cases import CalculateReturn, ComputeCorrelation, GetIntraday
from dse.features.analysis.domain import tools
from dse.features.analysis.domain.frames import Bar, LiveBar
from dse.shared_kernel.errors import NotFoundError, ValidationFailedError


def frame(closes: list[float], start: str = "2026-01-05") -> pd.DataFrame:  # a Monday; bdate_range is Mon-Fri
    idx = pd.bdate_range(start, periods=len(closes))
    return pd.DataFrame({"close": closes}, index=idx)


def test_return_applies_fees_on_both_legs_and_annualises() -> None:
    df = frame([100.0, 110.0, 120.0])  # Mon 5 .. Wed 7 Jan
    r = tools.return_between(df, date(2026, 1, 5), None, quantity=100, fee_pct=0.4)
    assert (r["buy_price"], r["sell_price"], r["days"]) == (100.0, 120.0, 2)
    assert r["cost"] == pytest.approx(100 * 100 * 1.004)
    assert r["proceeds"] == pytest.approx(120 * 100 * 0.996)
    assert r["profit"] == pytest.approx(r["proceeds"] - r["cost"])
    assert r["return_pct"] == pytest.approx((r["proceeds"] / r["cost"] - 1) * 100)
    assert r["annualised_pct"] == pytest.approx(((r["proceeds"] / r["cost"]) ** (365 / 2) - 1) * 100)


def test_return_picks_the_first_bar_on_or_after_buy_and_last_on_or_before_sell() -> None:
    df = frame([100.0, 101.0, 102.0, 103.0, 104.0])  # Mon 5 .. Fri 9 Jan
    # buy on a day before the first bar; sell on a day after the 4th
    r = tools.return_between(df, date(2026, 1, 3), date(2026, 1, 8), 1, 0)
    assert (r["buy_date"], r["sell_date"]) == ("2026-01-05", "2026-01-08")
    assert (r["buy_price"], r["sell_price"]) == (100.0, 103.0)
    zero = tools.return_between(df, date(2026, 1, 6), date(2026, 1, 6), 1, 0.4)  # same day: no annualisation
    assert zero["days"] == 0
    assert zero["annualised_pct"] is None
    assert zero["return_pct"] < 0  # fees only


def test_return_rejects_impossible_ranges() -> None:
    df = frame([100.0, 101.0, 102.0])
    for buy, sell in (
        (date(2027, 1, 1), None),
        (date(2026, 1, 7), date(2026, 1, 5)),
        (date(2020, 1, 1), date(2020, 6, 1)),
    ):
        with pytest.raises(ValidationFailedError, match="No bars between"):
            tools.return_between(df, buy, sell, 1, 0)
    with pytest.raises(ValidationFailedError):
        tools.return_between(frame([]), date(2026, 1, 1), None, 1, 0)


def test_correlation_of_returns() -> None:
    rng = np.random.default_rng(3)
    base = rng.normal(0, 0.01, 80)
    idx = pd.bdate_range("2026-01-04", periods=81)
    a = pd.Series(100 * np.cumprod(np.r_[1, 1 + base]), index=idx)
    b = pd.Series(50 * np.cumprod(np.r_[1, 1 + 2 * base]), index=idx)  # moves with a
    c = pd.Series(80 * np.cumprod(np.r_[1, 1 - base]), index=idx)  # moves against a
    out = tools.correlation({"A": a, "B": b, "C": c}, days=60)
    m = dict(zip(out["symbols"], out["matrix"], strict=True))
    assert out["days"] == 60
    assert m["A"][0] == pytest.approx(1.0)
    assert m["A"][1] > 0.99
    assert m["A"][2] < -0.99
    assert out["matrix"][1][0] == out["matrix"][0][1]  # symmetric


def test_correlation_needs_enough_shared_observations() -> None:
    idx = pd.bdate_range("2026-01-04", periods=10)
    short = pd.Series(np.linspace(1, 2, 10), index=idx)
    out = tools.correlation({"A": short, "B": short * 2}, days=120)
    assert out["matrix"][0][1] is None  # < 20 shared returns


# ------------------------------------------------------------------------------------------- use cases
@dataclass
class FakeHistory:
    daily: dict[str, tuple[Bar, ...]] = field(default_factory=dict)
    live: dict[str, LiveBar] = field(default_factory=dict)
    minutes: tuple[MinuteInput, ...] = ()
    asked: list[tuple[str, int]] = field(default_factory=list)

    async def bars(self, symbol: str, limit: int) -> tuple[Bar, ...]:
        self.asked.append((symbol, limit))
        return self.daily.get(symbol, ())

    async def live_bar(self, symbol: str) -> LiveBar | None:
        return self.live.get(symbol)

    async def minute_bars(self, symbol: str, day: date | None) -> tuple[MinuteInput, ...]:
        return self.minutes


def bars(closes: list[float], start: date = date(2026, 1, 4)) -> tuple[Bar, ...]:
    days = pd.bdate_range(start, periods=len(closes))
    return tuple(Bar(d.date(), c, c, c, c, 1000.0) for d, c in zip(days, closes, strict=True))


async def test_return_use_case_includes_todays_live_bar() -> None:
    history = FakeHistory(
        {"GP": bars([100.0, 110.0])},
        {"GP": LiveBar(date(2026, 1, 6), 130.0, 112.0, 131.0, 111.0, None, 5000.0, 10.0)},
    )
    out = await CalculateReturn(history)("GP", date(2026, 1, 4), None, 10, 0)
    assert (out.symbol, out.sell_date, out.sell_price) == (
        "GP",
        "2026-01-06",
        130.0,
    )  # today's live price, not the stale close
    assert out.return_pct == pytest.approx(30.0)
    with pytest.raises(NotFoundError):
        await CalculateReturn(history)("NOPE", date(2026, 1, 4), None, 10, 0)


async def test_correlation_use_case_dedupes_limits_and_skips_symbols_without_history() -> None:
    rng = np.random.default_rng(1)

    def walk() -> list[float]:
        return [float(x) for x in 100 * np.cumprod(1 + rng.normal(0, 0.01, 90))]

    history = FakeHistory({"A": bars(walk()), "B": bars(walk()), "C": bars(walk())})
    out = await ComputeCorrelation(history)(["A", "B", "A", "GHOST", "C"], 60)
    assert out.symbols == ["A", "B", "C"]
    assert [s for s, _ in history.asked] == ["A", "B", "GHOST", "C"]  # each symbol read once, in order
    assert {limit for _, limit in history.asked} == {65}
    with pytest.raises(ValidationFailedError, match="at least two"):
        await ComputeCorrelation(history)(["A", "GHOST"], 60)
    with pytest.raises(ValidationFailedError, match="At most 20"):
        await ComputeCorrelation(history)([f"S{i}" for i in range(21)], 60)


async def test_intraday_labels_minutes_with_vpa() -> None:
    t0 = datetime(2026, 11, 11, 10, 0, tzinfo=DHAKA)
    rng = np.random.default_rng(2)
    mins = [
        MinuteInput(t0 + timedelta(minutes=i), p, p + 0.2, p - 0.2, p, 1000.0 + rng.integers(0, 50))
        for i, p in enumerate(100 + np.cumsum(rng.normal(0, 0.05, 40)))
    ]
    last = mins[-1]  # a wide up bar on huge volume closing at its high: textbook "Strong buying"
    mins[-1] = MinuteInput(
        last.minute, last.close, last.close + 5, last.close - 0.05, last.close + 4.9, 9000.0
    )
    rows = await GetIntraday(FakeHistory(minutes=tuple(mins)))("GP")
    assert [r.time for r in rows[:2]] == ["10:00", "10:01"]
    assert len(rows) == 40
    assert rows[-1].vpa == "Strong buying"
    assert rows[0].vpa is None  # not enough history for a label yet
    assert await GetIntraday(FakeHistory())("GP") == []
