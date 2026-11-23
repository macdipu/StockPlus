"""The published Picks back-test: a JSON file written by `python -m dse.cli backtest-picks --out ...`."""

import json
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "picks_backtest.json"


class FileTrackRecord:
    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        self._path = path
        self._cached: tuple[float, dict[str, Any]] | None = None

    def load(self) -> dict[str, Any] | None:
        try:
            mtime = self._path.stat().st_mtime
        except OSError:
            return None
        if self._cached is None or self._cached[0] != mtime:  # re-read when a new run is published
            try:
                self._cached = (mtime, dict(json.loads(self._path.read_text())))
            except (OSError, ValueError):
                return None
        return self._cached[1]
