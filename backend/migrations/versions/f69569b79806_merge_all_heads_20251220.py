"""merge_all_heads_20251220

Revision ID: f69569b79806
Revises: 0001_convert_timestamps_to_timestamptz, 20251020_merge_heads, 20251220_add_performance_indexes
Create Date: 2025-12-20 10:01:41.862411

"""

# revision identifiers, used by Alembic.
revision = "f69569b79806"
down_revision = (
    "0001_convert_timestamps_to_timestamptz",
    "20251020_merge_heads",
    "20251220_add_performance_indexes",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
