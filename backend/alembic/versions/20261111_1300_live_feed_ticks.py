"""live feed: ticks (recorded quote changes, the source for intraday bars)

Revision ID: 0003_live_feed
Revises: 0002_market_data
Create Date: 2026-11-11 13:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_live_feed"
down_revision = "0002_market_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ticks",
        sa.Column("symbol", sa.String(24), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trade_time", sa.String(40)),
        sa.Column("ltp", sa.Numeric(14, 4)),
        sa.Column("high", sa.Numeric(14, 4)),
        sa.Column("low", sa.Numeric(14, 4)),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("value_mn", sa.Numeric(18, 4)),
        sa.Column("trades", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("symbol", "ts", name="pk_ticks"),
    )
    op.create_index("ix_ticks_ts", "ticks", ["ts"])


def downgrade() -> None:
    op.drop_index("ix_ticks_ts", table_name="ticks")
    op.drop_table("ticks")
