"""The materialised universe: one analysed row per instrument, in two views.

`live`        today's session with the live quote merged in (default for most scans)
`last_close`  the last completed session, quotes ignored (pre-market scans)
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd

from dse.shared_kernel.errors import ServiceNotReadyError


def rows_to_frame(rows: Sequence[dict[str, Any]], errors: dict[str, str] | None = None) -> pd.DataFrame:
    """Frame indexed by symbol while keeping 'symbol' as a column (so it can be sorted/filtered on)."""
    u = pd.DataFrame(list(rows))
    if not u.empty:
        u = u.set_index("symbol", drop=False)
        u.index.name = None
    u.attrs["errors"] = dict(errors or {})
    return u


@dataclass(frozen=True)
class Universe:
    version: int
    built_at_ms: int
    build_ms: int
    session_day: date | None
    trade_time: str | None
    live: pd.DataFrame
    last_close: pd.DataFrame
    errors: dict[str, str] = field(default_factory=dict)

    def frame(self, live: bool = True) -> pd.DataFrame:
        u = self.live if live else self.last_close
        if u.empty:
            raise ServiceNotReadyError(
                "The universe has no rows yet: run `python -m dse.cli backfill` to load history."
            )
        return u
