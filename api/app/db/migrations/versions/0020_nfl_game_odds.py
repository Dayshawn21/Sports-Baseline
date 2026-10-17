"""Store append-only NFL game-odds snapshots for the projection model.

Revision ID: 0020
Revises: 0019
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0020"
down_revision: Union[str, Sequence[str], None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nfl_game_odds",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("game_id", sa.BigInteger, sa.ForeignKey("nfl_games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("book", sa.Text, nullable=False),
        sa.Column("market", sa.Text, nullable=False),
        sa.Column("line", sa.Numeric(7, 2), nullable=True),
        sa.Column("first_side", sa.Text, nullable=False),
        sa.Column("second_side", sa.Text, nullable=False),
        sa.Column("first_odds", sa.Integer, nullable=False),
        sa.Column("second_odds", sa.Integer, nullable=False),
        sa.Column("first_market_prob", sa.Float, nullable=False),
        sa.Column("second_market_prob", sa.Float, nullable=False),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("raw_json", JSONB, nullable=True),
        sa.CheckConstraint("market IN ('moneyline', 'spread', 'total')", name="ck_nfl_game_odds_market"),
        sa.CheckConstraint("first_side <> second_side", name="ck_nfl_game_odds_distinct_sides"),
    )
    op.create_index("idx_nfl_game_odds_lookup", "nfl_game_odds", ["game_id", "book", "market", "fetched_at"])
    op.create_index("idx_nfl_game_odds_fetched", "nfl_game_odds", ["fetched_at"])


def downgrade() -> None:
    op.drop_index("idx_nfl_game_odds_fetched", table_name="nfl_game_odds")
    op.drop_index("idx_nfl_game_odds_lookup", table_name="nfl_game_odds")
    op.drop_table("nfl_game_odds")
