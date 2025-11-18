"""
Legacy alias module for early migration name.

This file now functions as a minimal Alembic revision to avoid loader errors when
Alembic scans the versions directory. It does not change the schema itself; the
real migration logic is contained in subsequent revisions.

Revision ID: 0001
Revises: None
Create Date: 2025-10-18
"""

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # No-op: this legacy marker exists only to satisfy Alembic's script loader.
    pass


def downgrade():
    # No-op: marker revision.
    pass
