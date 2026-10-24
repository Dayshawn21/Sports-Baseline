"""Store immutable ESPN NHL injury and starting-goalie batches.

Revision ID: 0050
Revises: 0049
"""
from alembic import op
import sqlalchemy as sa

revision: str = "0050"
down_revision: str = "0049"
branch_labels: None = None
depends_on: None = None

_PLAYER_REASONS = "'matched', 'no_candidate', 'ambiguous', 'team_mismatch', 'missing_team', 'position_mismatch', 'not_reported'"
_EVENT_REASONS = "'matched', 'no_game', 'ambiguous', 'missing_start', 'start_mismatch'"


def upgrade() -> None:
    op.create_table(
        "nhl_context_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("scope_date", sa.Date(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.UniqueConstraint("source", "kind", "scope_date", "fetched_at",
                            name="uq_nhl_context_batch", postgresql_nulls_not_distinct=True),
        sa.CheckConstraint("source = 'ESPN'", name="ck_nhl_context_source"),
        sa.CheckConstraint("entry_count >= 0", name="ck_nhl_context_count"),
        sa.CheckConstraint(
            "(kind = 'injuries' AND scope_date IS NULL AND source_timestamp IS NOT NULL) OR "
            "(kind = 'goalies' AND scope_date IS NOT NULL)", name="ck_nhl_context_scope",
        ),
    )
    op.create_index("ix_nhl_context_latest", "nhl_context_snapshots",
                    ["kind", "scope_date", sa.text("fetched_at DESC"), sa.text("id DESC")])
    _create_injuries()
    _create_goalies()


def _create_injuries() -> None:
    op.create_table(
        "nhl_player_injuries",
        sa.Column("snapshot_id", sa.BigInteger(), sa.ForeignKey("nhl_context_snapshots.id"), nullable=False),
        sa.Column("espn_team_id", sa.Text(), nullable=False),
        sa.Column("team_code", sa.String(8), nullable=False),
        sa.Column("espn_athlete_id", sa.Text(), nullable=False),
        sa.Column("player_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("return_date", sa.Text(), nullable=True),
        sa.Column("athlete_team_id", sa.Text(), nullable=True),
        sa.Column("player_id", sa.BigInteger(), sa.ForeignKey("sport_players.id"), nullable=True),
        sa.Column("link_reason", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("snapshot_id", "espn_team_id", "espn_athlete_id"),
        sa.CheckConstraint(f"link_reason IN ({_PLAYER_REASONS})", name="ck_nhl_injury_link_reason"),
        sa.CheckConstraint("(player_id IS NOT NULL) = (link_reason = 'matched')", name="ck_nhl_injury_link"),
    )
    op.create_index("ix_nhl_injury_snapshot_team", "nhl_player_injuries", ["snapshot_id", "team_code"])


def _create_goalies() -> None:
    op.create_table(
        "nhl_goalie_observations",
        sa.Column("snapshot_id", sa.BigInteger(), sa.ForeignKey("nhl_context_snapshots.id"), nullable=False),
        sa.Column("espn_event_id", sa.Text(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("time_valid", sa.Boolean(), nullable=False),
        sa.Column("home_team", sa.String(8), nullable=False),
        sa.Column("away_team", sa.String(8), nullable=False),
        sa.Column("espn_team_id", sa.Text(), nullable=False),
        sa.Column("team_code", sa.String(8), nullable=False),
        sa.Column("espn_athlete_id", sa.Text(), nullable=True),
        sa.Column("player_name", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("raw_status", sa.Text(), nullable=True),
        sa.Column("athlete_team_id", sa.Text(), nullable=True),
        sa.Column("source_position", sa.Text(), nullable=True),
        sa.Column("player_id", sa.BigInteger(), sa.ForeignKey("sport_players.id"), nullable=True),
        sa.Column("player_link_reason", sa.Text(), nullable=False),
        sa.Column("game_id", sa.BigInteger(), sa.ForeignKey("sport_games.id"), nullable=True),
        sa.Column("game_link_reason", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("snapshot_id", "espn_event_id", "espn_team_id"),
        sa.CheckConstraint("status IN ('expected', 'confirmed', 'unknown', 'not_reported')", name="ck_nhl_goalie_status"),
        sa.CheckConstraint(f"player_link_reason IN ({_PLAYER_REASONS})", name="ck_nhl_goalie_player_reason"),
        sa.CheckConstraint(f"game_link_reason IN ({_EVENT_REASONS})", name="ck_nhl_goalie_game_reason"),
        sa.CheckConstraint("(player_id IS NOT NULL) = (player_link_reason = 'matched')", name="ck_nhl_goalie_player_link"),
        sa.CheckConstraint("(game_id IS NOT NULL) = (game_link_reason = 'matched')", name="ck_nhl_goalie_game_link"),
        sa.CheckConstraint("time_valid OR game_id IS NULL", name="ck_nhl_goalie_time_valid"),
        sa.CheckConstraint("home_team <> away_team AND team_code IN (home_team, away_team)", name="ck_nhl_goalie_teams"),
        sa.CheckConstraint(
            "(status = 'not_reported' AND espn_athlete_id IS NULL AND player_name IS NULL "
            "AND raw_status IS NULL AND athlete_team_id IS NULL AND source_position IS NULL "
            "AND player_link_reason = 'not_reported') OR "
            "(status <> 'not_reported' AND espn_athlete_id IS NOT NULL AND player_name IS NOT NULL "
            "AND raw_status IS NOT NULL AND player_link_reason <> 'not_reported')", name="ck_nhl_goalie_announcement",
        ),
    )
    op.create_index("ix_nhl_goalie_snapshot_game", "nhl_goalie_observations", ["snapshot_id", "game_id", "team_code"])


def downgrade() -> None:
    op.drop_table("nhl_goalie_observations")
    op.drop_table("nhl_player_injuries")
    op.drop_table("nhl_context_snapshots")
