"""ORM models. Infrastructure-only: mapped to/from domain entities in repositories."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from dse.core.db import Base


class TickRow(Base):
    """Append-only; no updated_at. One row per (symbol, observed change)."""

    __tablename__ = "ticks"
    symbol: Mapped[str] = mapped_column(String(24), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    trade_time: Mapped[str | None] = mapped_column(String(40))
    ltp: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    high: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    low: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    volume: Mapped[int] = mapped_column(BigInteger)
    value_mn: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    trades: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_ticks_ts", "ts"),)
