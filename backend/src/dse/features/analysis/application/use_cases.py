"""Analysis use cases (queries). CPU-bound pandas work runs in a worker thread (event loop stays free)."""

import asyncio
from collections.abc import Sequence
from typing import Any

from dse.features.analysis.application.brief import render_brief
from dse.features.analysis.application.dto import (
    AnalysisDto,
    ScreenerRowDto,
    TechnicalBarDto,
    VpaDto,
    VpaRowDto,
)
from dse.features.analysis.application.knowledge import build, clean, day, num, technical_bars
from dse.features.analysis.application.ports import AnalysisInputs
from dse.features.analysis.domain import vpa
from dse.shared_kernel.errors import DomainError


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
