"""Register NHL and store skater and goalie game stats (item 45b).

Revision ID: 0049
Revises: 0048
"""
from alembic import op
import sqlalchemy as sa

revision: str = "0049"
down_revision: str = "0048"
branch_labels: None = None
depends_on: None = None

SKATER_TABLE = "nhl_skater_game_stats"
GOALIE_TABLE = "nhl_goalie_game_stats"
SKATER_STATS = (
    "goals", "assists", "points", "shots", "power_play_goals", "power_play_points",
    "shorthanded_points", "plus_minus", "hits", "blocked_shots", "faceoffs_won",
    "faceoffs_lost", "penalty_minutes", "giveaways", "takeaways", "ot_goals",
)


def _shared_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("player_id", sa.BigInteger, sa.ForeignKey("sport_players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_id", sa.BigInteger, sa.ForeignKey("sport_games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("sport_teams.id"), nullable=False),
        sa.Column("opponent_team_id", sa.BigInteger, sa.ForeignKey("sport_teams.id"), nullable=False),
        sa.Column("season", sa.SmallInteger, nullable=False),
        sa.Column("is_home", sa.Boolean, nullable=False),
        sa.Column("time_on_ice_seconds", sa.Integer, nullable=True),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.execute("INSERT INTO sports (code, name) VALUES ('nhl', 'NHL')")
    op.add_column("sport_games", sa.Column("end_period", sa.String(3), nullable=True))
    op.create_check_constraint("ck_sport_games_end_period", "sport_games", "end_period IN ('REG', 'OT', 'SO')")
    op.create_check_constraint("ck_sport_games_nhl_end_period", "sport_games", "sport = 'nhl' OR end_period IS NULL")

    op.create_table(
        SKATER_TABLE,
        *_shared_columns(),
        sa.Column("position", sa.Text, nullable=True),
        *(sa.Column(column, sa.SmallInteger, nullable=True) for column in SKATER_STATS),
        sa.UniqueConstraint("player_id", "game_id", name="uq_nhl_skater_game_stats_player_game"),
    )
    op.create_table(
        GOALIE_TABLE,
        *_shared_columns(),
        sa.Column("started", sa.Boolean, nullable=False),
        sa.Column("decision", sa.Text, nullable=True),
        *(sa.Column(column, sa.SmallInteger, nullable=True) for column in ("saves", "shots_against", "goals_against")),
        sa.CheckConstraint("decision IN ('W', 'L', 'O')", name="ck_nhl_goalie_game_stats_decision"),
        sa.UniqueConstraint("player_id", "game_id", name="uq_nhl_goalie_game_stats_player_game"),
    )
    for table in (SKATER_TABLE, GOALIE_TABLE):
        op.create_index(f"ix_{table}_player_season", table, ["player_id", "season"])
        op.create_index(f"ix_{table}_game", table, ["game_id"])


def downgrade() -> None:
    op.drop_table(GOALIE_TABLE)
    op.drop_table(SKATER_TABLE)
    op.drop_constraint("ck_sport_games_nhl_end_period", "sport_games", type_="check")
    op.drop_constraint("ck_sport_games_end_period", "sport_games", type_="check")
    op.drop_column("sport_games", "end_period")
    # Existing NHL rows must block removal of their sport, never cascade away.
    op.execute("DELETE FROM sports WHERE code = 'nhl'")
