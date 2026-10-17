"""Store historical NFLverse game lines and venue context.

Revision ID: 0028
Revises: 0027
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: Union[str, Sequence[str], None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("nfl_games", sa.Column("spread_line", sa.Numeric(), nullable=True))
    op.add_column("nfl_games", sa.Column("total_line", sa.Numeric(), nullable=True))
    op.add_column("nfl_games", sa.Column("home_moneyline", sa.Integer(), nullable=True))
    op.add_column("nfl_games", sa.Column("away_moneyline", sa.Integer(), nullable=True))
    op.add_column("nfl_games", sa.Column("roof", sa.Text(), nullable=True))
    op.add_column("nfl_games", sa.Column("home_rest", sa.SmallInteger(), nullable=True))
    op.add_column("nfl_games", sa.Column("away_rest", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("nfl_games", "away_rest")
    op.drop_column("nfl_games", "home_rest")
    op.drop_column("nfl_games", "roof")
    op.drop_column("nfl_games", "away_moneyline")
    op.drop_column("nfl_games", "home_moneyline")
    op.drop_column("nfl_games", "total_line")
    op.drop_column("nfl_games", "spread_line")
