"""Company use cases. Orchestration only: parsing in infrastructure, ratios in the domain."""

import asyncio
import dataclasses
import logging
from typing import Any

from dse.features.company.application.ports import AnalysisLookup, BarSource, CompanySources, PriceLookup
from dse.features.company.application.serialize import dossier_to_dict, with_price
from dse.features.company.domain.alerts import Alert, alerts_for
from dse.features.company.domain.entities import (
    AmarStockPart,
    CompanyDossier,
    SourceStatus,
    StockNowPart,
    TopStockPart,
)
from dse.shared_kernel.clock import Clock
from dse.shared_kernel.errors import ValidationFailedError

log = logging.getLogger("dse.company")


class GetCompanyDossier:
    """The three sources are fetched concurrently and independently (the source adapter caches them)."""

    def __init__(self, sources: CompanySources, prices: PriceLookup, clock: Clock) -> None:
        self._sources, self._prices, self._clock = sources, prices, clock
        self._inflight: dict[str, asyncio.Task[CompanyDossier]] = {}

    async def __call__(self, symbol: str, refresh: bool = False) -> dict[str, Any]:
        price = await self._prices.last_price(symbol)
        key = f"{symbol}|{refresh}"
        task = self._inflight.get(key)
        if task is None:  # single-flight: concurrent requests for one symbol share one fetch
            task = asyncio.create_task(self._fetch(symbol, refresh))
            self._inflight[key] = task
            task.add_done_callback(lambda _t: self._inflight.pop(key, None))
        dossier = await asyncio.shield(task)
        return with_price(dossier_to_dict(dossier), dossier, price)

    async def _fetch(self, symbol: str, refresh: bool) -> CompanyDossier:
        names = ("stocknow", "amarstock", "topstock")
        results = await asyncio.gather(
            self._sources.stocknow(symbol, refresh),
            self._sources.amarstock(symbol, refresh),
            self._sources.topstock(symbol, refresh),
            return_exceptions=True,
        )
        status = []
        for name, r in zip(names, results, strict=True):
            err = None if not isinstance(r, BaseException) else (str(r) or type(r).__name__)
            if err:
                log.warning("company source failed", extra={"symbol": symbol, "source": name, "error": err})
            status.append(
                SourceStatus(name=name, ok=err is None, url=self._sources.url(name, symbol), error=err)
            )
        sn, am, ts = results
        return CompanyDossier(
            symbol=symbol,
            fetched_at=self._clock.now().isoformat(timespec="seconds"),
            stocknow=sn if isinstance(sn, StockNowPart) else StockNowPart(),
            amarstock=am if isinstance(am, AmarStockPart) else AmarStockPart(),
            topstock=ts if isinstance(ts, TopStockPart) else TopStockPart(),
            sources=tuple(status),
        )


RESOLUTIONS = {"1": "1 minute", "5": "5 minutes", "30": "30 minutes", "60": "1 hour", "D": "1 day"}


class GetBars:
    """OHLCV candles at an intraday or daily resolution (the chart's timeframe tabs)."""

    def __init__(self, source: BarSource) -> None:
        self._source = source

    async def __call__(self, symbol: str, resolution: str, pages: int = 1) -> list[dict[str, Any]]:
        if resolution not in RESOLUTIONS:
            raise ValidationFailedError(f"resolution must be one of {', '.join(RESOLUTIONS)}")
        return await self._source.bars(symbol, resolution, max(1, min(pages, 4)))


class GetWatchlistAlerts:
    """Alerts for a list of symbols: buy zone with a bullish candle, stop broken, target hit, breakout,
    bearish candle. Dividend dates come from the company dossier when it is ready within a few seconds."""

    MAX_SYMBOLS = 30
    DOSSIER_WAIT_S = 6.0

    def __init__(self, analysis: AnalysisLookup, dossier: GetCompanyDossier, clock: Clock) -> None:
        self._analysis, self._dossier, self._clock = analysis, dossier, clock

    async def __call__(self, symbols: list[str]) -> list[dict[str, Any]]:
        wanted = list(dict.fromkeys(symbols))[: self.MAX_SYMBOLS]
        sem = asyncio.Semaphore(4)

        async def one(sym: str) -> list[Alert]:
            async with sem:
                try:
                    a = await self._analysis.analysis(sym)
                except Exception as e:
                    log.info("alert analysis failed", extra={"symbol": sym, "error": str(e)})
                    return []
            events: dict[str, Any] | None = None
            dividends: list[dict[str, Any]] = []
            try:
                d = await asyncio.wait_for(self._dossier(sym), self.DOSSIER_WAIT_S)
                events, dividends = d.get("events"), d.get("dividends") or []
            except Exception as e:  # the dividend note is optional
                log.info("alert dossier skipped", extra={"symbol": sym, "error": str(e)})
            return alerts_for(a, events, dividends, self._clock.today())

        results = await asyncio.gather(*(one(s) for s in wanted))
        return [dataclasses.asdict(x) for r in results for x in r]
