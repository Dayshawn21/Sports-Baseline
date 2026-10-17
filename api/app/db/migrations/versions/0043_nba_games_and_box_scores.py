"""Register NBA as a sport and store its per-game player box scores (item 20b).

Games, teams and players live in the shared `sport_*` tables under
`sport = 'nba'`; only the box scores are NBA-shaped, so they get their own
table like the `nfl_*` stat tables. NULL stats mean not loaded or did not
play, never zero.

Revision ID: 0043
Revises: 0042
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0043"
down_revision: Union[str, Sequence[str], None] = "0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "nba_player_game_stats"
STAT_COLUMNS = (
    "points", "rebounds", "offensive_rebounds", "defensive_rebounds", "assists", "steals", "blocks",
    "turnovers", "fouls", "field_goals_made", "field_goals_attempted", "three_pointers_made",
    "three_pointers_attempted", "free_throws_made", "free_throws_attempted", "plus_minus",
)


def upgrade() -> None:
    op.execute("INSERT INTO sports (code, name) VALUES ('nba', 'NBA')")
    # ESPN's NBA codes are the team key (20a), and Utah's is UTAH.
    op.alter_column("sport_teams", "team_code", type_=sa.String(8), existing_nullable=False)
    op.create_table(
        TABLE,
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("player_id", sa.BigInteger, sa.ForeignKey("sport_players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_id", sa.BigInteger, sa.ForeignKey("sport_games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("sport_teams.id"), nullable=False),
        sa.Column("opponent_team_id", sa.BigInteger, sa.ForeignKey("sport_teams.id"), nullable=False),
        sa.Column("season", sa.SmallInteger, nullable=False),
        sa.Column("is_home", sa.Boolean, nullable=False),
        sa.Column("starter", sa.Boolean, nullable=False),
        sa.Column("did_not_play", sa.Boolean, nullable=False),
        sa.Column("dnp_reason", sa.Text, nullable=True),
        sa.Column("minutes", sa.REAL, nullable=True),
        *(sa.Column(column, sa.SmallInteger, nullable=True) for column in STAT_COLUMNS),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("player_id", "game_id", name="uq_nba_player_game_stats_player_game"),
    )
    op.create_index("ix_nba_player_game_stats_player_season", TABLE, ["player_id", "season"])
    op.create_index("ix_nba_player_game_stats_game", TABLE, ["game_id"])


def downgrade() -> None:
    op.drop_table(TABLE)
    # Fails on the sports foreign key while any sport_* row is still NBA's, by design.
    op.execute("DELETE FROM sports WHERE code = 'nba'")
    op.alter_column("sport_teams", "team_code", type_=sa.String(3), existing_nullable=False)
