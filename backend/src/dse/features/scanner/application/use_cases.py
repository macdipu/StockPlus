"""Scanner use cases.

Write side (worker): MaterialiseUniverse (+ the single-flight UniverseRefresher).
Read side (API replicas): scans, presets, and the market analytics tables — all over the in-memory frames.
"""

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass, replace
from typing import Any

from dse.features.analysis.application.facade import UniverseInput, build_universe_rows
from dse.features.scanner.application.dto import (
    FieldsDto,
    PresetDto,
    RuleDto,
    ScanResultDto,
    UniverseStatusDto,
)
from dse.features.scanner.application.ports import (
    StoredUniverse,
    UniverseNotifier,
    UniverseSource,
    UniverseStore,
)
from dse.features.scanner.application.view import UniverseView
from dse.features.scanner.domain import analytics, picks
from dse.features.scanner.domain.fields import DEFAULT_COLUMNS, FIELD_DOCS
from dse.features.scanner.domain.picks import PickFilter
from dse.features.scanner.domain.presets import PRESETS
from dse.features.scanner.domain.rules import ALL_OPS, Preset, ScanSpec, UniverseFilter, run_scan
from dse.shared_kernel.clock import Clock
from dse.shared_kernel.errors import NotFoundError

log = logging.getLogger("dse.scanner")


# ================================================================================ write side (worker)
@dataclass(frozen=True, slots=True)
class BuildReport:
    version: int
    rows: int
    errors: int
    build_ms: int
    rebuilt_last_close: bool


class MaterialiseUniverse:
    """Build both universe views and publish them. Heavy pandas work runs in threads; history is cached and
    reloaded only when its signature changes, and the last-close view is rebuilt only when it could differ."""

    def __init__(
        self, source: UniverseSource, store: UniverseStore, notifier: UniverseNotifier, clock: Clock
    ) -> None:
        self._source, self._store, self._notifier, self._clock = source, store, notifier, clock
        self._history: list[UniverseInput] | None = None
        self._signature: Hashable = None
        self._last_key: Hashable = None
        self._last_rows: Any = None

    async def __call__(self) -> BuildReport:
        t0 = time.perf_counter()
        signature = await self._source.history_signature()
        if self._history is None or signature != self._signature:
            self._history, self._signature, self._last_key = (
                await self._source.load_history(),
                signature,
                None,
            )
        history = self._history
        state = await self._source.live_state()

        with_quotes = [replace(i, quote=state.quotes.get(i.symbol)) for i in history]
        live = await asyncio.to_thread(
            build_universe_rows, with_quotes, live=True, session_day=state.session_day
        )
        key = (signature, state.session_day)
        rebuilt = key != self._last_key
        if rebuilt:  # the last completed session only changes when history (or the session day) does
            self._last_rows = await asyncio.to_thread(
                build_universe_rows, history, live=False, session_day=state.session_day
            )
            self._last_key = key
        build_ms = int((time.perf_counter() - t0) * 1000)
        version = await self._store.save(
            StoredUniverse(
                built_at_ms=int(self._clock.now().timestamp() * 1000),
                build_ms=build_ms,
                session_day=state.session_day,
                trade_time=state.trade_time,
                live_rows=live.rows,
                last_close_rows=self._last_rows.rows,
                errors={**live.errors, **self._last_rows.errors},
            )
        )
        try:
            await self._notifier.built(version, len(live.rows), build_ms)
        except Exception as e:  # a notification failure must not undo a successful build
            log.warning("universe notification failed", extra={"error": f"{type(e).__name__}: {e}"})
        log.info("universe built", extra={"version": version, "rows": len(live.rows), "build_ms": build_ms})
        return BuildReport(version, len(live.rows), len(live.errors), build_ms, rebuilt)

    async def history_changed(self) -> bool:
        """Has stored history/fundamentals changed since the last build? (a backfill, a sync, an EOD write)"""
        return self._history is not None and await self._source.history_signature() != self._signature


class UniverseRefresher:
    """Single-flight trigger: calls while a build runs collapse into ONE extra build afterwards, and
    `trigger()` never blocks the caller (the poll loop)."""

    def __init__(
        self,
        build: MaterialiseUniverse,
        check_every_s: float = 30.0,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._build = build
        self._check_every_s, self._monotonic = check_every_s, monotonic
        self._last_check = monotonic()
        self._task: asyncio.Task[None] | None = None
        self._pending = False
        self.built_once = False

    def trigger(self) -> None:
        if self._task is not None and not self._task.done():
            self._pending = True
            return
        self._task = asyncio.create_task(self._run(), name="universe-refresh")

    async def on_poll(self, *, first: bool, changed: bool, market_changed: bool) -> None:
        """Rebuild when the market moved, until the first build has succeeded, or when stored history
        changed (checked at most every `check_every_s`: after hours there are no ticks, but a backfill
        still counts)."""
        if not self.built_once or first or changed or market_changed:
            self.trigger()
            return
        now = self._monotonic()
        if now - self._last_check >= self._check_every_s:
            self._last_check = now
            if await self._build.history_changed():
                self.trigger()

    async def _run(self) -> None:
        while True:
            self._pending = False
            try:
                await self._build()
                self.built_once = True
            except Exception:
                log.exception("universe build failed")
            if not self._pending:
                return

    async def join(self) -> None:
        """Wait for the running build (and any collapsed rebuild) to finish."""
        if self._task is not None:
            await self._task

    async def aclose(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task


# ================================================================================ read side (API)
def _result(
    u_version: int, trade_time: str | None, live: bool, scanned: int, hits: Any, cols: Any
) -> ScanResultDto:
    return ScanResultDto(
        rows=analytics.to_records(hits, cols or DEFAULT_COLUMNS),
        matched=len(hits),
        scanned=scanned,
        live=live,
        universe_version=u_version,
        trade_time=trade_time,
    )


class RunScan:
    def __init__(self, view: UniverseView) -> None:
        self._view = view

    async def __call__(
        self, spec: ScanSpec, columns: Sequence[str] | None = None, live: bool = True
    ) -> ScanResultDto:
        u = await self._view.current()
        frame = u.frame(live)
        return _result(u.version, u.trade_time, live, len(frame), run_scan(frame, spec), columns)


class RunPreset:
    def __init__(self, view: UniverseView) -> None:
        self._view = view

    async def __call__(
        self,
        key: str,
        universe: UniverseFilter,
        limit: int = 100,
        columns: Sequence[str] | None = None,
        live: bool | None = None,
    ) -> tuple[ScanResultDto, Preset]:
        preset = PRESETS.get(key)
        if preset is None:
            raise NotFoundError(f"No preset '{key}'. See /api/v1/scanner/presets")
        is_live = (not preset.premarket) if live is None else live
        u = await self._view.current()
        frame = u.frame(is_live)
        hits = run_scan(frame, preset.spec(universe, limit))
        return _result(u.version, u.trade_time, is_live, len(frame), hits, columns), preset


def _preset_dto(p: Preset) -> PresetDto:
    return PresetDto(
        key=p.key,
        name=p.name,
        group=p.group,
        description=p.description,
        premarket=p.premarket,
        match=p.match,
        rules=[RuleDto(field=r.field, op=r.op, value=r.value, field2=r.field2) for r in p.rules],
        sort_field=p.sort.field,
        sort_desc=p.sort.desc,
    )


class ListPresets:
    def __call__(self) -> list[PresetDto]:
        return [_preset_dto(p) for p in PRESETS.values()]


class ListFields:
    def __call__(self) -> FieldsDto:
        return FieldsDto(fields=FIELD_DOCS, ops=sorted(ALL_OPS), default_columns=list(DEFAULT_COLUMNS))


class _Analytics:
    def __init__(self, view: UniverseView) -> None:
        self._view = view


class GetSectors(_Analytics):
    async def __call__(self) -> list[dict[str, Any]]:
        return analytics.sectors((await self._view.current()).frame())


class GetPe(_Analytics):
    async def __call__(self) -> dict[str, Any]:
        return analytics.pe_summary((await self._view.current()).frame())


class GetRange52w(_Analytics):
    COLUMNS = (
        "symbol",
        "sector",
        "ltp",
        "low_52w",
        "high_52w",
        "range_position_pct",
        "pct_from_52w_high",
        "pct_from_52w_low",
    )

    async def __call__(self, near: str = "high", limit: int = 100) -> list[dict[str, Any]]:
        frame = (await self._view.current()).frame()
        return analytics.to_records(analytics.range_52w(frame, near, limit), self.COLUMNS)


class GetTable(_Analytics):
    """A per-instrument table over chosen columns (TA values, fundamentals/valuation matrix)."""

    async def __call__(self, columns: Sequence[str], sector: str | None = None) -> list[dict[str, Any]]:
        frame = (await self._view.current()).frame()
        if sector:
            frame = frame[frame["sector"] == sector]
        return analytics.to_records(frame.sort_values("symbol"), columns)


class GetPicks(_Analytics):
    """Every instrument ranked for value and entry timing, bucketed (see domain.picks)."""

    async def __call__(self, flt: PickFilter, live: bool = True) -> dict[str, Any]:
        u = await self._view.current()
        frame = u.frame(live)
        everything = await asyncio.to_thread(
            picks.rank, frame, flt, False
        )  # ~400 rows of Python: off the loop
        counts = dict.fromkeys(picks.BUCKETS, 0)
        for r in everything:
            counts[r["bucket"]] += 1
        rows = everything[: flt.limit]
        return {
            "rows": rows,
            "counts": counts,
            "sectors": list(picks.sector_names(frame)),
            "universe_version": u.version,
            "trade_time": u.trade_time,
            "live": live,
            "method": picks.__doc__,
        }


class GetUniverseStatus:
    def __init__(self, view: UniverseView) -> None:
        self._view = view

    async def __call__(self) -> UniverseStatusDto:
        u = await self._view.peek()
        if u is None:
            return UniverseStatusDto(
                ready=False,
                version=None,
                rows=0,
                built_at_ms=None,
                build_ms=None,
                session_day=None,
                trade_time=None,
                errors={},
            )
        return UniverseStatusDto(
            ready=not u.live.empty,
            version=u.version,
            rows=len(u.live),
            built_at_ms=u.built_at_ms,
            build_ms=u.build_ms,
            session_day=u.session_day,
            trade_time=u.trade_time,
            errors=u.errors,
        )
