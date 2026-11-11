"""ORM models. Infrastructure-only: mapped to/from domain entities in repositories."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, Enum, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dse.core.db import Base
from dse.features.market_data.domain.entities import BarSource


class Audited:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InstrumentRow(Audited, Base):
    __tablename__ = "instruments"
    symbol: Mapped[str] = mapped_column(String(24), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    sector: Mapped[str | None] = mapped_column(String(60))
    category: Mapped[str | None] = mapped_column(String(4))
    board: Mapped[str | None] = mapped_column(String(20))
    asset_type: Mapped[str | None] = mapped_column(String(8))
    isin: Mapped[str | None] = mapped_column(String(20))
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class FundamentalsRow(Audited, Base):
    __tablename__ = "fundamentals"
    symbol: Mapped[str] = mapped_column(String(24), primary_key=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)


class DailyBarRow(Audited, Base):
    __tablename__ = "daily_bars"
    symbol: Mapped[str] = mapped_column(String(24), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    high: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    low: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    close: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    volume: Mapped[int] = mapped_column(BigInteger)
    trades: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[BarSource] = mapped_column(
        Enum(BarSource, name="bar_source", values_callable=lambda e: [m.value for m in e])
    )
    __table_args__ = (Index("ix_daily_bars_day", "day"),)


class AnnouncementRow(Audited, Base):
    __tablename__ = "announcements"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(24), index=True)
    published_on: Mapped[date | None] = mapped_column(Date)
    kind: Mapped[str | None] = mapped_column(String(40))
    title: Mapped[str | None] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
