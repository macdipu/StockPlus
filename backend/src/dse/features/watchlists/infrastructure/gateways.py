"""Adapters over other features' public facades (ARCHITECTURE §4.3)."""

from collections.abc import Sequence
from typing import Any

from dse.features.live_feed.application.facade import LiveFeedFacade
from dse.features.scanner.application.facade import ScannerFacade
from dse.shared_kernel.errors import ValidationFailedError


class LiveFeedSymbolDirectory:
    """A symbol is real iff DSE's live snapshot lists it (~400 codes, present even when the market is
    closed). If the feed has no snapshot yet this raises ServiceNotReadyError (503) rather than guessing."""

    def __init__(self, live: LiveFeedFacade) -> None:
        self._live = live

    async def ensure_known(self, symbols: Sequence[str]) -> None:
        if not symbols:
            return
        known = {q.symbol for q in await self._live.quotes(list(symbols))}
        missing = [s for s in symbols if s not in known]
        if missing:
            raise ValidationFailedError(f"Not a DSE trading code: {', '.join(missing)}", unknown=missing)


class ScannerScanValidator:
    def __init__(self, scanner: ScannerFacade) -> None:
        self._scanner = scanner

    def validate(self, definition: Any) -> None:
        self._scanner.validate_scan(definition)
