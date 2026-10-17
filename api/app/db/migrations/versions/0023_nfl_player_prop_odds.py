"""Store append-only sportsbook player-prop price snapshots for NFL games.

Revision ID: 0023
Revises: 0022
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0023"
down_revision: Union[str, Sequence[str], None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nfl_player_prop_odds",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("game_id", sa.BigInteger, sa.ForeignKey("nfl_games.id", ondelete="CASCADE"), nullable=False),
        # Nullable: a book name that does not resolve is kept, not guessed.
        sa.Column("player_id", sa.BigInteger, sa.ForeignKey("nfl_players.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider_player_name", sa.Text, nullable=False),
        sa.Column("provider_event_id", sa.Text, nullable=False),
        sa.Column("market", sa.Text, nullable=False),
        sa.Column("book", sa.Text, nullable=False),
        sa.Column("line", sa.Numeric(7, 2), nullable=True),
        sa.Column("yes_odds", sa.Integer, nullable=False),
        sa.Column("no_odds", sa.Integer, nullable=True),
        sa.Column("market_prob", sa.Float, nullable=False),
        sa.Column("includes_margin", sa.Boolean, nullable=False),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("raw_json", JSONB, nullable=True),
        sa.CheckConstraint("market IN ('anytime_touchdown')", name="ck_nfl_player_prop_odds_market"),
        sa.CheckConstraint("market_prob > 0 AND market_prob < 1", name="ck_nfl_player_prop_odds_prob"),
    )
    op.create_index(
        "idx_nfl_player_prop_odds_lookup", "nfl_player_prop_odds",
        ["game_id", "market", "player_id", "fetched_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_nfl_player_prop_odds_lookup", table_name="nfl_player_prop_odds")
    op.drop_table("nfl_player_prop_odds")
