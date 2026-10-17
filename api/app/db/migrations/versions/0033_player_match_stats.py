"""player_match_stats

Persist exact player-oriented TennisAbstract match box scores used by the
Tennis Props evidence panel and future offline feature validation.
"""

from alembic import op
import sqlalchemy as sa


revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_match_stats",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("player_id", sa.BigInteger, sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("source_match_key", sa.Text, nullable=False),
        sa.Column("match_date", sa.Date, nullable=False),
        sa.Column("surface", sa.Text, nullable=True),
        sa.Column("result", sa.Text, nullable=True),
        sa.Column("aces", sa.SmallInteger, nullable=True),
        sa.Column("double_faults", sa.SmallInteger, nullable=True),
        sa.Column("service_games", sa.SmallInteger, nullable=True),
        sa.Column("break_points_faced", sa.SmallInteger, nullable=True),
        sa.Column("break_points_saved", sa.SmallInteger, nullable=True),
        sa.Column("break_chances_created", sa.SmallInteger, nullable=True),
        sa.Column("break_points_converted", sa.SmallInteger, nullable=True),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("player_id", "source", "source_match_key", name="uq_player_match_stats_source"),
    )
    op.create_index("idx_player_match_stats_recent", "player_match_stats", ["player_id", "match_date"])


def downgrade() -> None:
    op.drop_index("idx_player_match_stats_recent", table_name="player_match_stats")
    op.drop_table("player_match_stats")
