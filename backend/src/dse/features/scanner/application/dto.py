"""Application-boundary DTOs for the scanner."""

from datetime import date
from typing import Any

from pydantic import BaseModel


class ScanResultDto(BaseModel):
    rows: list[dict[str, Any]]
    matched: int
    scanned: int
    live: bool
    universe_version: int
    trade_time: str | None


class RuleDto(BaseModel):
    field: str
    op: str
    value: Any = None
    field2: str | None = None


class PresetDto(BaseModel):
    key: str
    name: str
    group: str
    description: str
    premarket: bool
    match: str
    rules: list[RuleDto]
    sort_field: str
    sort_desc: bool


class FieldsDto(BaseModel):
    fields: dict[str, str]
    ops: list[str]
    default_columns: list[str]


class UniverseStatusDto(BaseModel):
    ready: bool
    version: int | None
    rows: int
    built_at_ms: int | None
    build_ms: int | None
    session_day: date | None
    trade_time: str | None
    errors: dict[str, str]
