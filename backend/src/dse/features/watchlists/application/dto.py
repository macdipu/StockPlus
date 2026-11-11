"""Application-boundary DTOs."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class WatchlistDto(BaseModel):
    id: UUID
    name: str
    symbols: list[str]
    created_at: datetime
    updated_at: datetime


class SavedScanDto(BaseModel):
    id: UUID
    name: str
    definition: dict[str, Any]
    created_at: datetime
    updated_at: datetime
