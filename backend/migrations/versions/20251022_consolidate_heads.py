"""
Merge all current heads into a single linear history.

Revision ID: 20251022_consolidate_heads
Revises: 20251020_merge_heads, 20251021_add_backfill_runs
Create Date: 2025-10-22
"""

# revision identifiers, used by Alembic.
revision = "20251022_consolidate_heads"
down_revision = ("20251020_merge_heads", "20251021_add_backfill_runs")
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge revision; no schema changes required.
    pass


def downgrade():
    # Downgrade is intentionally a no-op for merge.
    pass
