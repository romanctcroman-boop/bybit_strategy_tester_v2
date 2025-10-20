"""Merge revision to unify multiple heads

Revision ID: 20251020_merge_heads
Revises: 2f4e6a7b8c9d, 20251020_add_bybit_kline_audit
Create Date: 2025-10-20
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '20251020_merge_heads'
down_revision = ('2f4e6a7b8c9d', '20251020_add_bybit_kline_audit')
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge revision; no schema changes required — it consolidates heads.
    pass


def downgrade():
    # Downgrade is intentionally a no-op for merge
    pass
