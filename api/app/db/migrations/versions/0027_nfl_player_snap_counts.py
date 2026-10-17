"""Store per-game NFL offensive snap counts and snap share per player.

A separate table rather than columns on `nfl_player_weekly_stats`: many
player-games have snaps but no stat line (blocking tight ends), and those are
exactly the role evidence snap share exists to capture.

Revision ID: 0027
Revises: 0026
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: Union[str, Sequence[str], None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nfl_player_snap_counts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("player_id", sa.BigInteger, sa.ForeignKey("nfl_players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_id", sa.BigInteger, sa.ForeignKey("nfl_games.id", ondelete="CASCADE"), nullable=False),
        # Copied from the game so as-of queries can bound by (season, week) without a join.
        sa.Column("season", sa.SmallInteger, nullable=False),
        sa.Column("week", sa.SmallInteger, nullable=False),
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("nfl_teams.id"), nullable=False),
        # NULL when the source left the value blank; 0 means no offensive snaps.
        sa.Column("offense_snaps", sa.SmallInteger, nullable=True),
        sa.Column("offense_pct", sa.REAL, nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("player_id", "game_id", name="uq_nfl_player_snap_counts_player_game"),
    )
    op.create_index(
        "ix_nfl_player_snap_counts_player_season_week", "nfl_player_snap_counts", ["player_id", "season", "week"],
    )


def downgrade() -> None:
    op.drop_index("ix_nfl_player_snap_counts_player_season_week", table_name="nfl_player_snap_counts")
    op.drop_table("nfl_player_snap_counts")
