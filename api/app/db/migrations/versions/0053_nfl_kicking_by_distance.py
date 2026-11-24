"""Store field goals made and missed by distance band, and missed PATs (item 27l1).

PrizePicks scores a field goal by distance (0-39 yds +3, 40-49 +4, 50+ +5), so
kicker fantasy points cannot be built from `fg_made` alone. Names match the
NFLverse weekly stats file verbatim. NULL means not loaded, never zero.

Revision ID: 0053
Revises: 0052
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0053"
down_revision: Union[str, Sequence[str], None] = "0052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BANDS = ("0_19", "20_29", "30_39", "40_49", "50_59", "60_")
COLUMNS = (
    *(f"fg_made_{band}" for band in BANDS),
    *(f"fg_missed_{band}" for band in BANDS),
    "pat_missed",
)


def upgrade() -> None:
    for column in COLUMNS:
        op.add_column("nfl_player_weekly_stats", sa.Column(column, sa.SmallInteger, nullable=True))


def downgrade() -> None:
    for column in reversed(COLUMNS):
        op.drop_column("nfl_player_weekly_stats", column)
