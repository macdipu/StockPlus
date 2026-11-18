"""Charts use cases. Orchestration only: maths in dse.indicators, I/O behind ports.

Indicator output is cached under a key made of the symbol, resolution, the candles' content fingerprint and
the requested indicators. New candles mean a new key, so nothing is ever invalidated. Concurrent requests for
one key share one computation, and the CPU work runs in a thread behind a concurrency cap.
"""

import asyncio
import hashlib
import json
import math
from dataclasses import dataclass

import numpy as np

from dse.features.charts.application.dto import (
    CandlesDto,
    CatalogDto,
    CatalogEntryDto,
    ChartDto,
    IndicatorDto,
    OutputDto,
    ParamDto,
)
from dse.features.charts.application.ports import ChartCache
from dse.features.charts.application.sources import RoutedCandles
from dse.features.charts.domain.candles import Candles, check_resolution
from dse.features.charts.domain.chart import IndicatorResult, run_indicators
from dse.features.charts.domain.spec import ResolvedSpec, parse_specs, spec_hash
from dse.indicators import REGISTRY
from dse.indicators.requirements import required_columns
from dse.shared_kernel.errors import NotFoundError

ENGINE_REV = 1  # bump when an indicator's maths changes without its id changing (invalidates cached output)
GROUP_ORDER = ("Moving averages", "Bands and channels", "Trend", "Momentum", "Volatility", "Volume", "Price")
TTL_S = {"1": 3600, "5": 3600, "30": 6 * 3600, "60": 6 * 3600, "D": 6 * 3600}
MAX_PAGES = 4


def build_catalog() -> CatalogDto:
    entries = [
        CatalogEntryDto(
            id=i.id,
            name=i.name,
            group=i.group,
            placement=i.placement,
            description=i.description,
            params=[
                ParamDto(key=p.key, label=p.label, default=p.default, min=p.min, max=p.max, integer=p.integer)
                for p in i.params
            ],
            outputs=[OutputDto(key=o.key, label=o.label, kind=o.kind) for o in i.outputs],
            scale=i.scale,
            levels=list(i.levels),
            repaints=i.repaints,
            requires=list(required_columns(i.id)),
        )
        for i in REGISTRY.values()
    ]
    rank = {g: n for n, g in enumerate(GROUP_ORDER)}
    entries.sort(key=lambda e: (rank.get(e.group, 99), e.name.lower()))
    version = hashlib.blake2b(
        f"{ENGINE_REV}{json.dumps([e.model_dump() for e in entries], sort_keys=True)}".encode(), digest_size=6
    ).hexdigest()
    return CatalogDto(
        version=version,
        groups=[g for g in GROUP_ORDER if any(e.group == g for e in entries)],
        indicators=entries,
    )


class ListIndicators:
    def __init__(self) -> None:
        self._catalog = build_catalog()  # static for the life of the process

    def __call__(self) -> CatalogDto:
        return self._catalog


def _series(values: np.ndarray) -> list[float | None]:
    rounded = np.round(values, 6)
    return [None if not math.isfinite(v) else float(v) for v in rounded.tolist()]


def build_chart(
    symbol: str, resolution: str, source: str, candles: Candles, specs: list[ResolvedSpec], version: str
) -> ChartDto:
    results: list[IndicatorResult]
    warnings: list[str] = []
    runnable = specs
    if not candles.ohlc:  # closing values only: say what cannot be drawn instead of drawing nonsense
        runnable = []
        for s in specs:
            missing = required_columns(s.indicator.id)
            if missing:
                warnings.append(
                    f"{s.indicator.name} needs {', '.join(missing)}, which this series does not have"
                )
            else:
                runnable.append(s)
    results, failed = run_indicators(candles, runnable)
    warnings += failed
    return ChartDto(
        symbol=symbol,
        resolution=resolution,
        source=source,
        ohlc=candles.ohlc,
        candles=CandlesDto(
            time=candles.time.tolist(),
            open=candles.open.tolist(),
            high=candles.high.tolist(),
            low=candles.low.tolist(),
            close=candles.close.tolist(),
            volume=candles.volume.tolist(),
        ),
        indicators=[
            IndicatorDto(
                key=r.spec.key,
                id=r.spec.indicator.id,
                name=r.spec.indicator.name,
                group=r.spec.indicator.group,
                placement=r.spec.indicator.placement,
                params=dict(r.spec.params),
                outputs=[OutputDto(key=o.key, label=o.label, kind=o.kind) for o in r.spec.indicator.outputs],
                scale=r.spec.indicator.scale,
                levels=list(r.spec.indicator.levels),
                repaints=r.spec.indicator.repaints,
                series={c: _series(r.values[c].to_numpy()) for c in r.values.columns},
            )
            for r in results
        ],
        warnings=warnings,
        catalog_version=version,
    )


@dataclass(frozen=True, slots=True)
class ChartResult:
    etag: str
    chart: ChartDto | None  # None = the client's copy is current (HTTP 304)


class GetChart:
    def __init__(
        self, sources: RoutedCandles, cache: ChartCache, catalog: ListIndicators, max_concurrent: int = 4
    ) -> None:
        self._sources, self._cache, self._catalog = sources, cache, catalog
        self._sem = asyncio.Semaphore(max_concurrent)
        self._inflight: dict[str, asyncio.Task[ChartDto]] = {}

    async def __call__(
        self,
        symbol: str,
        resolution: str,
        indicators: str | None,
        pages: int = 1,
        if_none_match: str | None = None,
    ) -> ChartResult:
        check_resolution(resolution)
        specs = parse_specs(indicators)
        candles = await self._sources.candles(symbol, resolution, max(1, min(pages, MAX_PAGES)))
        if len(candles) == 0:
            source = self._sources.source_name(symbol, resolution)
            hint = (
                " Intraday candles are built from prices this app records during market hours."
                if source == "recorded-ticks"
                else ""
            )
            raise NotFoundError(f"No candles for {symbol} at resolution {resolution}.{hint}", symbol=symbol)
        version = self._catalog().version
        key = f"chart:{version}:{symbol}:{resolution}:{candles.fingerprint()}:{spec_hash(specs)}"
        etag = f'W/"{hashlib.blake2b(key.encode(), digest_size=8).hexdigest()}"'
        if if_none_match is not None and etag in {t.strip() for t in if_none_match.split(",")}:
            return ChartResult(etag, None)
        cached = await self._cache.get(key)
        if cached is not None:
            return ChartResult(etag, ChartDto.model_validate(cached))
        task = self._inflight.get(key)
        if task is None:  # single flight: concurrent requests for one key share one computation
            task = asyncio.create_task(self._compute(key, symbol, resolution, candles, specs, version))
            self._inflight[key] = task
            task.add_done_callback(lambda _t: self._inflight.pop(key, None))
        return ChartResult(etag, await asyncio.shield(task))

    async def _compute(
        self,
        key: str,
        symbol: str,
        resolution: str,
        candles: Candles,
        specs: list[ResolvedSpec],
        version: str,
    ) -> ChartDto:
        source = self._sources.source_name(symbol, resolution)
        async with self._sem:
            chart = await asyncio.to_thread(build_chart, symbol, resolution, source, candles, specs, version)
        await self._cache.put(key, chart.model_dump(mode="json"), TTL_S[resolution])
        return chart
