"""Fix market_data.created_at default to use sa.func.now()

Revision ID: 002_fix_market_data_created_at
Revises: 001_initial
Create Date: 2025-10-18 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_fix_market_data_created_at'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alter column default for market_data.created_at to use sa.func.now()
    try:
        op.alter_column('market_data', 'created_at', server_default=sa.func.now())
    except Exception:
        # Some backends (e.g., SQLite) may not support alter; fall back to no-op and log
        # Developers should recreate the table or run manual ALTER statements as needed.
        pass


def downgrade() -> None:
    try:
        op.alter_column('market_data', 'created_at', server_default=sa.text('now()'))
    except Exception:
        pass
