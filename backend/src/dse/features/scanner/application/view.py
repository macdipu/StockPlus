"""Read-side cache of the published universe. One per API replica.

A request costs one cheap version lookup; the frames are rebuilt only when the worker published a new
version (about once a minute), so scans run on in-memory frames.
"""

import asyncio

from dse.features.scanner.application.ports import StoredUniverse, UniverseStore
from dse.features.scanner.domain.universe import Universe, rows_to_frame
from dse.shared_kernel.errors import ServiceNotReadyError


def to_universe(s: StoredUniverse) -> Universe:
    return Universe(
        version=s.version,
        built_at_ms=s.built_at_ms,
        build_ms=s.build_ms,
        session_day=s.session_day,
        trade_time=s.trade_time,
        live=rows_to_frame(s.live_rows, s.errors),
        last_close=rows_to_frame(s.last_close_rows, s.errors),
        errors=s.errors,
    )


class UniverseView:
    def __init__(self, store: UniverseStore) -> None:
        self._store = store
        self._cached: Universe | None = None
        self._lock = asyncio.Lock()

    async def current(self) -> Universe:
        version = await self._store.version()
        if version is None:
            raise ServiceNotReadyError("The universe has not been built yet; the worker builds it each tick.")
        cached = self._cached
        if cached is not None and cached.version == version:
            return cached
        async with self._lock:  # single-flight: concurrent requests share one reload
            cached = self._cached
            if cached is not None and cached.version == await self._store.version():
                return cached
            stored = await self._store.load()
            if stored is None:
                raise ServiceNotReadyError("The universe has not been built yet.")
            self._cached = await asyncio.to_thread(to_universe, stored)
            return self._cached

    async def peek(self) -> Universe | None:
        """Current universe, or None when nothing is published (for status endpoints)."""
        try:
            return await self.current()
        except ServiceNotReadyError:
            return None
