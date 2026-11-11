"""Watchlists and saved scans: user-owned data with real invariants. Pure Python."""

import json
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any
from uuid import UUID

from dse.shared_kernel.errors import ConflictError, ValidationFailedError
from dse.shared_kernel.symbol import Symbol

MAX_WATCHLISTS = 20
MAX_SYMBOLS = 100
MAX_SAVED_SCANS = 50
MAX_NAME = 60
MAX_DEFINITION_BYTES = 8_192


def normalise_name(raw: str) -> tuple[str, str]:
    """(display name, uniqueness key). Names are unique per user, ignoring case and surrounding space."""
    name = " ".join(raw.split())  # trims and collapses runs of whitespace
    if not 1 <= len(name) <= MAX_NAME:
        raise ValidationFailedError(f"Name must be 1 to {MAX_NAME} characters.")
    if any(ord(ch) < 32 for ch in name):
        raise ValidationFailedError("Name must not contain control characters.")
    return name, name.casefold()


def clean_symbols(raw: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Validated trading codes, upper-cased, duplicates dropped, first-seen order kept."""
    seen: dict[str, None] = {}
    for s in raw:
        seen.setdefault(Symbol(s).value, None)
    return tuple(seen)


@dataclass(frozen=True, slots=True)
class Watchlist:
    id: UUID
    owner_id: UUID
    name: str
    name_key: str
    symbols: tuple[str, ...]
    created_at: datetime
    updated_at: datetime

    def renamed(self, raw: str, now: datetime) -> "Watchlist":
        name, key = normalise_name(raw)
        return replace(self, name=name, name_key=key, updated_at=now)

    def with_symbols(self, raw: list[str] | tuple[str, ...], now: datetime) -> "Watchlist":
        symbols = clean_symbols(raw)
        if len(symbols) > MAX_SYMBOLS:
            raise ConflictError(f"A watchlist holds at most {MAX_SYMBOLS} symbols.")
        return replace(self, symbols=symbols, updated_at=now)

    def adding(self, raw: list[str], now: datetime) -> "Watchlist":
        """Idempotent: symbols already present keep their place; new ones go to the end."""
        return self.with_symbols([*self.symbols, *clean_symbols(raw)], now)

    def removing(self, symbol: str, now: datetime) -> "Watchlist":
        code = Symbol(symbol).value
        return replace(self, symbols=tuple(s for s in self.symbols if s != code), updated_at=now)


@dataclass(frozen=True, slots=True)
class SavedScan:
    id: UUID
    owner_id: UUID
    name: str
    name_key: str
    definition: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    def updated(self, name: str | None, definition: dict[str, Any] | None, now: datetime) -> "SavedScan":
        out = self
        if name is not None:
            n, key = normalise_name(name)
            out = replace(out, name=n, name_key=key)
        if definition is not None:
            check_definition_size(definition)
            out = replace(out, definition=definition)
        return replace(out, updated_at=now)


def check_definition_size(definition: dict[str, Any]) -> None:
    if len(json.dumps(definition, separators=(",", ":")).encode()) > MAX_DEFINITION_BYTES:
        raise ValidationFailedError(f"A scan definition may be at most {MAX_DEFINITION_BYTES} bytes.")
