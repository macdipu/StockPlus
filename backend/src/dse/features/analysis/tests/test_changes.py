"""What changed since the previous session: each rule on a hand-built row."""

from typing import Any

from dse.features.analysis.domain.changes import MAX_CHANGES, describe_changes


def row(**over: Any) -> dict[str, Any]:
    quiet: dict[str, Any] = {
        "close": 100.0,
        "close_prev": 100.0,
        "sma50": 90.0,
        "sma50_prev": 90.0,
        "sma200": 80.0,
        "sma200_prev": 80.0,
        "ema9": 101.0,
        "ema9_prev": 101.0,
        "ema21": 99.0,
        "ema21_prev": 99.0,
        "macd": 1.0,
        "macd_prev": 1.0,
        "macd_signal": 0.5,
        "macd_signal_prev": 0.5,
        "rsi14": 55.0,
        "rsi14_prev": 55.0,
        "change_pct": 0.3,
        "vol_ratio": 1.0,
        "patterns": [],
        "vpa": None,
        "new_52w_high": False,
        "breakout_20d": False,
        "breakdown_20d": False,
        "gap_up_pct": 0.0,
        "gap_down_pct": 0.0,
    }
    quiet.update(over)
    return quiet


def texts(r: dict[str, Any]) -> list[str]:
    return [c.text for c in describe_changes(r)]


def test_a_quiet_session_has_nothing_to_report() -> None:
    assert describe_changes(row()) == []


def test_crossing_the_200_day_average_is_the_headline() -> None:
    r = row(
        close=101.0, close_prev=99.5, sma200=100.0, sma200_prev=100.0
    )  # stays above the 21-day, so one change
    [c] = describe_changes(r)
    assert (c.kind, c.tone, c.weight) == ("cross_sma200", "good", 5)
    assert c.text == "Closed back above its 200-day average (100.00)."


def test_falling_below_an_average_is_bad_news() -> None:
    r = row(close=89.0, close_prev=91.0, sma50=90.0, sma50_prev=90.0)
    assert describe_changes(r)[0].text == "Closed below its 50-day average (90.00)."
    assert describe_changes(r)[0].tone == "bad"


def test_staying_on_one_side_is_not_a_change() -> None:
    assert describe_changes(row(close=95.0, close_prev=94.0, sma50=90.0, sma50_prev=89.0)) == []


def test_rsi_crossings() -> None:
    assert "fell into oversold" in texts(row(rsi14=28.0, rsi14_prev=31.0))[0]
    assert "climbed out of oversold" in texts(row(rsi14=32.0, rsi14_prev=29.0))[0]
    assert "rose into overbought" in texts(row(rsi14=72.0, rsi14_prev=69.0))[0]
    assert "moved above 50" in texts(row(rsi14=52.0, rsi14_prev=49.0))[0]
    assert "moved below 50" in texts(row(rsi14=48.0, rsi14_prev=51.0))[0]


def test_macd_and_moving_average_crosses() -> None:
    assert any(
        "MACD crossed above" in t
        for t in texts(row(macd=0.6, macd_prev=0.4, macd_signal=0.5, macd_signal_prev=0.5))
    )
    assert any(
        "9-day average crossed below" in t
        for t in texts(row(ema9=98.0, ema9_prev=100.0, ema21=99.0, ema21_prev=99.0))
    )


def test_breakouts_and_new_highs() -> None:
    assert texts(row(new_52w_high=True, breakout_20d=True)) == ["Hit a new 52-week high."]
    assert texts(row(breakout_20d=True)) == ["Closed above its 20-day high: a breakout."]
    assert texts(row(breakdown_20d=True)) == ["Closed below its 20-day low: a breakdown."]


def test_big_moves_gaps_and_volume_take_the_direction_of_the_move() -> None:
    up = describe_changes(row(change_pct=5.2, gap_up_pct=2.5, vol_ratio=2.4))
    assert [c.tone for c in up] == ["good", "good", "good"]
    down = {c.kind: c for c in describe_changes(row(change_pct=-4.5, vol_ratio=3.0))}
    assert down["big_move"].text == "Down 4.5% in the session."
    assert down["volume_spike"].tone == "bad"


def test_labels_and_candle_patterns_are_reported_with_their_bias() -> None:
    r = row(
        vpa="Strong selling",
        vpa_bias="bearish",
        patterns=["Bearish Engulfing"],
        bearish_pattern=True,
        bullish_pattern=False,
    )
    by = {c.kind: c for c in describe_changes(r)}
    assert by["vpa"].tone == "bad"
    assert by["pattern"].text == "Candle pattern on the last session: Bearish Engulfing."
    assert by["pattern"].tone == "bad"


def test_at_most_five_changes_most_important_first() -> None:
    r = row(
        close=101.0,
        close_prev=99.0,
        sma200=100.0,
        sma200_prev=100.0,
        rsi14=28.0,
        rsi14_prev=31.0,
        new_52w_high=True,
        change_pct=6.0,
        gap_up_pct=3.0,
        vol_ratio=3.0,
        vpa="Strong buying",
        vpa_bias="bullish",
        patterns=["Doji"],
        macd=0.6,
        macd_prev=0.4,
    )
    out = describe_changes(r)
    assert len(out) == MAX_CHANGES
    assert [c.weight for c in out] == sorted((c.weight for c in out), reverse=True)
    assert out[0].weight == 5


def test_missing_numbers_never_raise() -> None:
    assert describe_changes({}) == []
    assert describe_changes({"close": None, "rsi14": float("nan")}) == []


async def test_the_use_case_reports_changes_for_a_real_instrument(orion_input: Any) -> None:
    from dse.features.analysis.application.use_cases import GetChanges

    class Inputs:
        async def load(self, symbol: str) -> Any:
            return orion_input

    r = await GetChanges(Inputs())("ORIONINFU")
    assert r.enough_history
    assert r.symbol == "ORIONINFU"
    assert r.bar_date is not None
    assert r.previous_bar_date is not None
    assert r.previous_bar_date < r.bar_date
    assert len(r.changes) <= MAX_CHANGES
    assert all(c.text and c.tone in ("good", "bad", "info") for c in r.changes)


async def test_too_little_history_says_so_instead_of_guessing(orion_input: Any) -> None:
    from dataclasses import replace

    from dse.features.analysis.application.use_cases import GetChanges

    class Inputs:
        async def load(self, symbol: str) -> Any:
            return replace(orion_input, bars=orion_input.bars[:10])

    r = await GetChanges(Inputs())("ORIONINFU")
    assert r.enough_history is False
    assert r.changes == []
