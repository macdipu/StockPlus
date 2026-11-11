"""market data tables: instruments, fundamentals, daily_bars, announcements

Revision ID: 0002_market_data
Revises: 0001_baseline
Create Date: 2026-11-11 11:43
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_market_data"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

AUDIT = (
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)


def _audit() -> list[sa.Column[object]]:
    return [c.copy() for c in AUDIT]


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("symbol", sa.String(24), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("sector", sa.String(60)),
        sa.Column("category", sa.String(4)),
        sa.Column("board", sa.String(20)),
        sa.Column("asset_type", sa.String(8)),
        sa.Column("isin", sa.String(20)),
        sa.Column("synced_at", sa.DateTime(timezone=True)),
        *_audit(),
    )
    op.create_index("ix_instruments_synced_at", "instruments", ["synced_at"])
    op.create_table(
        "fundamentals",
        sa.Column("symbol", sa.String(24), primary_key=True),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        *_audit(),
    )
    bar_source = postgresql.ENUM("page", "snapshot", name="bar_source")
    op.create_table(
        "daily_bars",
        sa.Column("symbol", sa.String(24), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("open", sa.Numeric(14, 4), nullable=False),
        sa.Column("high", sa.Numeric(14, 4), nullable=False),
        sa.Column("low", sa.Numeric(14, 4), nullable=False),
        sa.Column("close", sa.Numeric(14, 4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("trades", sa.Integer()),
        sa.Column("source", bar_source, nullable=False),
        *_audit(),
    )
    op.create_index("ix_daily_bars_day", "daily_bars", ["day"])
    op.create_table(
        "announcements",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("symbol", sa.String(24), nullable=False),
        sa.Column("published_on", sa.Date()),
        sa.Column("kind", sa.String(40)),
        sa.Column("title", sa.String(300)),
        sa.Column("body", sa.Text(), nullable=False),
        *_audit(),
    )
    op.create_index("ix_announcements_symbol", "announcements", ["symbol"])


def downgrade() -> None:
    op.drop_table("announcements")
    op.drop_table("daily_bars")
    postgresql.ENUM(name="bar_source").drop(op.get_bind(), checkfirst=True)
    op.drop_table("fundamentals")
    op.drop_table("instruments")
