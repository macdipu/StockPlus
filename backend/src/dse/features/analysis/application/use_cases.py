"""Analysis use cases (queries). CPU-bound pandas work runs in a worker thread (event loop stays free)."""

import asyncio
from collections.abc import Sequence
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from dse.features.analysis.application.brief import render_brief
from dse.features.analysis.application.dto import (
    AnalysisDto,
    ChartLineDto,
    ChartPatternDto,
    ChartPointDto,
    CorrelationDto,
    IntradayBarDto,
    ReturnDto,
    ScreenerRowDto,
    TechnicalBarDto,
    VpaDto,
    VpaRowDto,
)
from dse.features.analysis.application.knowledge import build, clean, day, num, technical_bars
from dse.features.analysis.application.ports import AnalysisInputs, HistorySource
from dse.features.analysis.domain import chart_patterns, tools, vpa
from dse.features.analysis.domain.frames import merge_live, to_frame
from dse.shared_kernel.errors import DomainError, NotFoundError, ValidationFailedError


class AnalyzeInstrument:
    def __init__(self, inputs: AnalysisInputs) -> None:
        self._inputs = inputs

    async def knowledge(self, symbol: str) -> tuple[dict[str, Any], Any]:
        return await asyncio.to_thread(build, await self._inputs.load(symbol))

    async def __call__(self, symbol: str) -> AnalysisDto:
        k, _ = await self.knowledge(symbol)
        return AnalysisDto.model_validate(clean(k))


class GetBrief:
    def __init__(self, analyze: AnalyzeInstrument) -> None:
        self._analyze = analyze

    async def __call__(self, symbol: str) -> str:
        k, _ = await self._analyze.knowledge(symbol)
        return render_brief(clean(k))


class GetTechnicals:
    """Daily bars with moving averages / Bollinger bands (the chart series)."""

    def __init__(self, analyze: AnalyzeInstrument) -> None:
        self._analyze = analyze

    async def __call__(self, symbol: str, limit: int = 260) -> list[TechnicalBarDto]:
        _, ind = await self._analyze.knowledge(symbol)
        return [TechnicalBarDto.model_validate(b) for b in technical_bars(ind, limit)]


class GetVpa:
    def __init__(self, analyze: AnalyzeInstrument) -> None:
        self._analyze = analyze

    async def __call__(self, symbol: str, days: int = 60) -> VpaDto:
        _, ind = await self._analyze.knowledge(symbol)
        v = vpa.classify(ind).join(ind[["open", "high", "low", "close", "volume"]]).iloc[-days:]
        rows = [
            VpaRowDto(
                date=day(i),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r["volume"]),
                vpa=r["vpa"] if isinstance(r["vpa"], str) else None,
                vpa_bias=r["vpa_bias"] if isinstance(r["vpa_bias"], str) else None,
                spread_rel=num(r["spread_rel"]),
                vol_rel=num(r["vol_rel"]),
                close_pos=num(r["close_pos"]),
            )
            for i, r in v.iterrows()
        ]
        legend = {k: {"bias": b, "meaning": m} for k, (b, m) in vpa.LABELS.items()}
        return VpaDto(rows=rows, legend=legend, thresholds=dict(vpa.VT))


class RankSymbols:
    """Rank symbols by setup score, then risk/reward. Sequential on purpose: each cold symbol may hit DSE."""

    def __init__(self, analyze: AnalyzeInstrument) -> None:
        self._analyze = analyze

    async def __call__(self, symbols: Sequence[str]) -> list[ScreenerRowDto]:
        rows: list[dict[str, Any]] = []
        for sym in symbols:
            try:
                a = await self._analyze(sym)
                rows.append(
                    {
                        "symbol": sym,
                        "ltp": a.price["ltp"],
                        "action": a.signal.action,
                        "score": a.setup.score,
                        "rr": a.setup.plan.rr,
                        "p_target_first": a.probability.similar_setups.p_target_first,
                    }
                )
            except DomainError as e:
                rows.append({"symbol": sym, "action": "ERROR", "score": -1, "error": e.detail or str(e)})
        rows.sort(key=lambda r: (r["score"], r.get("rr") or 0), reverse=True)
        return [ScreenerRowDto(rank=i, **r) for i, r in enumerate(rows, 1)]


class CalculateReturn:
    def __init__(self, history: HistorySource) -> None:
        self._history = history

    async def __call__(
        self, symbol: str, buy: date, sell: date | None, quantity: float, fee_pct: float
    ) -> ReturnDto:
        bars = await self._history.bars(symbol, 2000)
        if not bars:
            raise NotFoundError(f"No price history for {symbol}.")
        df = merge_live(to_frame(bars), await self._history.live_bar(symbol))
        return ReturnDto(symbol=symbol, **tools.return_between(df, buy, sell, quantity, fee_pct))


class ComputeCorrelation:
    """Sequential on purpose: an unsynced symbol is fetched from DSE (politely spaced) the first time."""

    def __init__(self, history: HistorySource) -> None:
        self._history = history

    async def __call__(self, symbols: Sequence[str], days: int) -> CorrelationDto:
        unique = list(dict.fromkeys(symbols))
        if len(unique) > tools.MAX_CORRELATION_SYMBOLS:
            raise ValidationFailedError(f"At most {tools.MAX_CORRELATION_SYMBOLS} symbols.")
        closes = {}
        for sym in unique:
            bars = await self._history.bars(sym, days + 5)
            if bars:
                closes[sym] = to_frame(bars)["close"]
        if len(closes) < 2:
            raise ValidationFailedError("Need at least two symbols with price history.")
        return CorrelationDto.model_validate(tools.correlation(closes, days))


class GetIntraday:
    """1-minute bars recorded from the live feed, each labelled by volume-price analysis."""

    def __init__(self, history: HistorySource) -> None:
        self._history = history

    async def __call__(self, symbol: str, day: date | None = None) -> list[IntradayBarDto]:
        minutes = await self._history.minute_bars(symbol, day)
        if not minutes:
            return []
        frame = pd.DataFrame(
            [
                {"open": m.open, "high": m.high, "low": m.low, "close": m.close, "volume": m.volume}
                for m in minutes
            ],
            index=pd.DatetimeIndex([m.minute for m in minutes]),
        )
        labels = vpa.classify(frame)["vpa"]
        return [
            IntradayBarDto(
                time=f"{m.minute:%H:%M}",
                open=m.open,
                high=m.high,
                low=m.low,
                close=m.close,
                volume=m.volume,
                vpa=label if isinstance(label, str) else None,
            )
            for m, label in zip(minutes, labels, strict=True)
        ]


class GetChartPatterns:
    """Possible chart patterns (double top/bottom, head and shoulders, triangles, channels, wedges, ranges)
    on the latest daily bars. Rule-based and approximate; the CPU work runs in a thread."""

    BARS = 300

    def __init__(self, history: HistorySource) -> None:
        self._history = history

    async def __call__(self, symbol: str) -> list[ChartPatternDto]:
        bars = await self._history.bars(symbol, self.BARS)
        if len(bars) < 40:
            return []
        days = [b.day for b in bars]
        high = np.array([b.high for b in bars], dtype=float)
        low = np.array([b.low for b in bars], dtype=float)
        close = np.array([b.close for b in bars], dtype=float)
        found = await asyncio.to_thread(chart_patterns.detect, days, high, low, close)

        def point(p: chart_patterns.Point) -> ChartPointDto:
            return ChartPointDto(day=p.day, price=round(p.price, 2), label=p.label)

        return [
            ChartPatternDto(
                kind=f.kind,
                name=f.name,
                direction=f.direction,
                status=f.status,
                confidence=f.confidence,
                start=f.start,
                end=f.end,
                points=[point(p) for p in f.points],
                lines=[ChartLineDto(role=ln.role, a=point(ln.a), b=point(ln.b)) for ln in f.lines],
                summary=f.summary,
            )
            for f in found
        ]
