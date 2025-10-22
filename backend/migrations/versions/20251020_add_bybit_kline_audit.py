"""create bybit_kline_audit table

Revision ID: 20251020_add_bybit_kline_audit
Revises:
Create Date: 2025-10-20 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20251020_add_bybit_kline_audit"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bybit_kline_audit",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("open_time", sa.BigInteger, nullable=False),
        sa.Column("open_time_dt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("open_price", sa.Float, nullable=True),
        sa.Column("high_price", sa.Float, nullable=True),
        sa.Column("low_price", sa.Float, nullable=True),
        sa.Column("close_price", sa.Float, nullable=True),
        sa.Column("volume", sa.Float, nullable=True),
        sa.Column("turnover", sa.Float, nullable=True),
        sa.Column("raw", sa.Text, nullable=False),
        sa.Column(
            "inserted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_unique_constraint(
        "uix_symbol_open_time", "bybit_kline_audit", ["symbol", "open_time"]
    )


def downgrade():
    op.drop_constraint("uix_symbol_open_time", "bybit_kline_audit", type_="unique")
    op.drop_table("bybit_kline_audit")
