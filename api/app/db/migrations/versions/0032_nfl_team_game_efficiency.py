"""Store per-team, per-game offensive efficiency sums from NFLverse play-by-play.

Revision ID: 0032
Revises: 0031
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: Union[str, Sequence[str], None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nfl_team_game_efficiency",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("game_id", sa.BigInteger, sa.ForeignKey("nfl_games.id", ondelete="CASCADE"), nullable=False),
        # The offense. Defense for a team-game is the opponent's row.
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("nfl_teams.id", ondelete="CASCADE"), nullable=False),
        # Copied from the game so as-of queries can bound by (season, week) without a join.
        sa.Column("season", sa.SmallInteger, nullable=False),
        sa.Column("week", sa.SmallInteger, nullable=False),
        sa.Column("is_home", sa.Boolean, nullable=False),
        sa.Column("plays", sa.SmallInteger, nullable=False),
        # Summed, not averaged, so windows and seasons aggregate exactly.
        sa.Column("epa", sa.Float, nullable=False),
        sa.Column("successes", sa.SmallInteger, nullable=False),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("game_id", "team_id", name="uq_nfl_team_game_efficiency_game_team"),
    )
    op.create_index("ix_nfl_team_game_efficiency_season_week", "nfl_team_game_efficiency", ["season", "week"])


def downgrade() -> None:
    op.drop_index("ix_nfl_team_game_efficiency_season_week", table_name="nfl_team_game_efficiency")
    op.drop_table("nfl_team_game_efficiency")
