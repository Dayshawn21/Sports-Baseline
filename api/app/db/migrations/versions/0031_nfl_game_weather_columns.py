"""Store NFLverse recorded game temperature and wind on nfl_games.

These are observed game conditions, filled only after a game is played, not a
pre-game forecast. NULL for indoor games and when the source is blank.

Revision ID: 0031
Revises: 0030
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: Union[str, Sequence[str], None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("nfl_games", sa.Column("temp", sa.SmallInteger(), nullable=True))
    op.add_column("nfl_games", sa.Column("wind", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("nfl_games", "wind")
    op.drop_column("nfl_games", "temp")
