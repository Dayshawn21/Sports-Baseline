"""Normalized NFL team-sport and player-prop storage foundation.

Tennis tables remain unchanged. NFL is deliberately separate while the app gains
team-sport support, avoiding a risky rewrite of working tennis assumptions.

Revision ID: 0015
Revises: 0014
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "0015"
down_revision: Union[str, Sequence[str], None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nfl_teams",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("team_code", sa.String(3), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("conference", sa.String(3), nullable=True),
        sa.Column("division", sa.String(16), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_nfl_teams_code", "nfl_teams", ["team_code"], unique=True)

    op.create_table(
        "nfl_players",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("nflverse_id", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("position", sa.String(8), nullable=True),
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("nfl_teams.id"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_nfl_players_nflverse_id", "nfl_players", ["nflverse_id"], unique=True)
    op.create_index("idx_nfl_players_team", "nfl_players", ["team_id"])

    op.create_table(
        "nfl_games",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("nflverse_game_id", sa.Text, nullable=False),
        sa.Column("season", sa.SmallInteger, nullable=False),
        sa.Column("week", sa.SmallInteger, nullable=False),
        sa.Column("game_type", sa.String(3), nullable=False),
        sa.Column("game_date", sa.Date, nullable=False),
        sa.Column("start_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("home_team_id", sa.BigInteger, sa.ForeignKey("nfl_teams.id"), nullable=False),
        sa.Column("away_team_id", sa.BigInteger, sa.ForeignKey("nfl_teams.id"), nullable=False),
        sa.Column("home_score", sa.SmallInteger, nullable=True),
        sa.Column("away_score", sa.SmallInteger, nullable=True),
        sa.Column("status", sa.Text, server_default="scheduled", nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_nfl_games_provider", "nfl_games", ["nflverse_game_id"], unique=True)
    op.create_index("idx_nfl_games_slate", "nfl_games", ["season", "week", "game_date"])

    op.create_table(
        "nfl_player_weekly_stats",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("player_id", sa.BigInteger, sa.ForeignKey("nfl_players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_id", sa.BigInteger, sa.ForeignKey("nfl_games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("nfl_teams.id"), nullable=False),
        sa.Column("opponent_team_id", sa.BigInteger, sa.ForeignKey("nfl_teams.id"), nullable=True),
        sa.Column("season", sa.SmallInteger, nullable=False),
        sa.Column("week", sa.SmallInteger, nullable=False),
        sa.Column("passing_yards", sa.Integer, server_default="0", nullable=False),
        sa.Column("passing_attempts", sa.SmallInteger, server_default="0", nullable=False),
        sa.Column("passing_completions", sa.SmallInteger, server_default="0", nullable=False),
        sa.Column("rushing_yards", sa.Integer, server_default="0", nullable=False),
        sa.Column("rushing_attempts", sa.SmallInteger, server_default="0", nullable=False),
        sa.Column("receiving_yards", sa.Integer, server_default="0", nullable=False),
        sa.Column("receptions", sa.SmallInteger, server_default="0", nullable=False),
        sa.Column("touchdowns", sa.SmallInteger, server_default="0", nullable=False),
        sa.Column("fantasy_points", sa.Numeric(7, 2), nullable=True),
        sa.Column("source", sa.Text, server_default="nflverse", nullable=False),
        sa.Column("raw_json", JSONB, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("player_id", "game_id", name="uq_nfl_player_game_stats"),
    )
    op.create_index("idx_nfl_weekly_stats_player", "nfl_player_weekly_stats", ["player_id", "season", "week"])

    op.create_table(
        "nfl_prop_lines",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column("provider_prop_id", sa.Text, nullable=True),
        sa.Column("player_id", sa.BigInteger, sa.ForeignKey("nfl_players.id"), nullable=True),
        sa.Column("game_id", sa.BigInteger, sa.ForeignKey("nfl_games.id"), nullable=True),
        sa.Column("market", sa.Text, nullable=False),
        sa.Column("line", sa.Numeric(7, 2), nullable=False),
        sa.Column("over_odds", sa.Integer, nullable=True),
        sa.Column("under_odds", sa.Integer, nullable=True),
        sa.Column("start_time", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("raw_json", JSONB, nullable=True),
    )
    op.create_index("idx_nfl_prop_lines_slate", "nfl_prop_lines", ["player_id", "market", "fetched_at"])
    op.create_index("idx_nfl_prop_lines_provider", "nfl_prop_lines", ["provider", "provider_prop_id"])

    op.create_table(
        "nfl_prop_predictions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("prop_line_id", sa.BigInteger, sa.ForeignKey("nfl_prop_lines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_version", sa.Text, nullable=False),
        sa.Column("projection", sa.Numeric(7, 2), nullable=False),
        sa.Column("p_over", sa.Float, nullable=False),
        sa.Column("p_under", sa.Float, nullable=False),
        sa.Column("edge", sa.Float, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("quality_flags", ARRAY(sa.Text), nullable=True),
        sa.Column("feature_snapshot", JSONB, nullable=True),
        sa.Column("generated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_nfl_prop_predictions_line", "nfl_prop_predictions", ["prop_line_id", "generated_at"])

    op.create_table(
        "nfl_prop_results",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("prop_line_id", sa.BigInteger, sa.ForeignKey("nfl_prop_lines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actual_value", sa.Numeric(7, 2), nullable=True),
        sa.Column("outcome", sa.String(8), nullable=False),
        sa.Column("graded_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("prop_line_id", name="uq_nfl_prop_result_line"),
    )


def downgrade() -> None:
    op.drop_table("nfl_prop_results")
    op.drop_table("nfl_prop_predictions")
    op.drop_table("nfl_prop_lines")
    op.drop_table("nfl_player_weekly_stats")
    op.drop_table("nfl_games")
    op.drop_table("nfl_players")
    op.drop_table("nfl_teams")
