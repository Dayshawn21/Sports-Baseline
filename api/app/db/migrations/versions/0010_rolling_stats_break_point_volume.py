"""rolling_stats_break_point_volume

Adds break-point opportunity volume fields to player_rolling_stats.
"""

from alembic import op
import sqlalchemy as sa


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("player_rolling_stats", sa.Column("break_points_created_per_return_game", sa.Numeric(7, 4), nullable=True))
    op.add_column("player_rolling_stats", sa.Column("allowed_break_points_per_service_game", sa.Numeric(7, 4), nullable=True))


def downgrade() -> None:
    op.drop_column("player_rolling_stats", "allowed_break_points_per_service_game")
    op.drop_column("player_rolling_stats", "break_points_created_per_return_game")
