"""Fix Trade.backtest_id type: Integer → String(36) + add created_at index

Revision ID: 20260401_fix_trade_backtest_id
Revises: 20260304_backtest_extend
Create Date: 2026-04-01

Problem:
    Trade.backtest_id was declared as Integer, but Backtest.id is String(36) (UUID).
    In SQLite the mismatch was silent (dynamic typing + FK constraints off by default).
    In PostgreSQL the FK constraint would fail on any Trade insert.

Fix:
    - Rename the column to the correct type via batch_alter_table (SQLite-safe).
    - Add index on created_at for time-range queries.
    - Add composite index (backtest_id, created_at) for JOIN + ORDER BY patterns.

Notes:
    batch_alter_table recreates the table under the hood — safe for SQLite.
    For PostgreSQL, ALTER COLUMN TYPE is used directly (no recreation needed,
    but existing integer values are cast to text, which is always safe).
"""

import sqlalchemy as sa
from alembic import op

revision = "20260401_fix_trade_backtest_id"
down_revision = "20260304_backtest_extend"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        # SQLite cannot ALTER COLUMN TYPE directly — use batch mode (table recreation).
        with op.batch_alter_table("trades", recreate="always") as batch_op:
            batch_op.alter_column(
                "backtest_id",
                existing_type=sa.Integer(),
                type_=sa.String(36),
                existing_nullable=False,
            )
            batch_op.create_index("ix_trades_created_at", ["created_at"])
            batch_op.create_index(
                "ix_trades_backtest_created", ["backtest_id", "created_at"]
            )
    else:
        # PostgreSQL / MySQL — ALTER COLUMN directly.
        op.alter_column(
            "trades",
            "backtest_id",
            existing_type=sa.Integer(),
            type_=sa.String(36),
            existing_nullable=False,
            postgresql_using="backtest_id::text",
        )
        op.create_index("ix_trades_created_at", "trades", ["created_at"])
        op.create_index(
            "ix_trades_backtest_created", "trades", ["backtest_id", "created_at"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("trades", recreate="always") as batch_op:
            batch_op.drop_index("ix_trades_backtest_created")
            batch_op.drop_index("ix_trades_created_at")
            batch_op.alter_column(
                "backtest_id",
                existing_type=sa.String(36),
                type_=sa.Integer(),
                existing_nullable=False,
            )
    else:
        op.drop_index("ix_trades_backtest_created", table_name="trades")
        op.drop_index("ix_trades_created_at", table_name="trades")
        op.alter_column(
            "trades",
            "backtest_id",
            existing_type=sa.String(36),
            type_=sa.Integer(),
            existing_nullable=False,
            postgresql_using="backtest_id::integer",
        )
