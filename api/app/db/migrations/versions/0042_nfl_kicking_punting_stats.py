"""Store field goals, extra points and punts per player-game (item 34b).

They settle the line-only PrizePicks markets FG Made (`fg_made`), Kicking Points
(`3 * fg_made + pat_made`) and Punts (`punts`). `fg_made` and `pat_made` come
from the NFLverse weekly stats file; `punts` comes from play-by-play under the
red-zone contract (zero for every row in a loaded game). NULL means not loaded,
never zero.

Revision ID: 0042
Revises: 0041
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0042"
down_revision: Union[str, Sequence[str], None] = "0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = ("fg_made", "pat_made", "punts")


def upgrade() -> None:
    for column in COLUMNS:
        op.add_column("nfl_player_weekly_stats", sa.Column(column, sa.SmallInteger, nullable=True))


def downgrade() -> None:
    for column in reversed(COLUMNS):
        op.drop_column("nfl_player_weekly_stats", column)
