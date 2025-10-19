"""Add market_data.created_at column with default now()

Revision ID: 003_add_market_data_created_at_explicit
Revises: 002_fix_market_data_created_at
Create Date: 2025-10-19 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003_add_market_data_created_at_explicit'
down_revision = '002_fix_market_data_created_at'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add column created_at if missing and set default to now()
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if 'market_data' in insp.get_table_names():
        cols = [c['name'] for c in insp.get_columns('market_data')]
        if 'created_at' not in cols:
            op.add_column('market_data', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True))
            # For safety, set existing rows to now()
            try:
                conn.execute(sa.text("UPDATE market_data SET created_at = now() WHERE created_at IS NULL"))
            except Exception:
                pass
    else:
        # If table doesn't exist, we expect the initial migration to create it later in the chain
        pass


def downgrade() -> None:
    # Remove column if present
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if 'market_data' in insp.get_table_names():
        cols = [c['name'] for c in insp.get_columns('market_data')]
        if 'created_at' in cols:
            op.drop_column('market_data', 'created_at')