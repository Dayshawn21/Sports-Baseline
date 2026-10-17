"""Store the fantasy scoring components and PrizePicks fantasy points per player-game.

`fantasy_points` stays NFLverse PPR. PrizePicks charges -1, not -2, per
interception and lost fumble, and counts offensive fumble-recovery TDs, so its
lines settle on `prizepicks_fantasy_points`, computed at ingest by
`app.core.nfl_fantasy.prizepicks_fantasy_points`.
NULL means the row was ingested before this revision, never zero.

Revision ID: 0036
Revises: 0035
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: Union[str, Sequence[str], None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COUNT_COLUMNS = (
    "passing_tds", "interceptions", "fumbles_lost", "two_point_conversions", "return_tds", "fumble_recovery_tds",
)


def upgrade() -> None:
    for column in _COUNT_COLUMNS:
        op.add_column("nfl_player_weekly_stats", sa.Column(column, sa.SmallInteger, nullable=True))
    op.add_column("nfl_player_weekly_stats", sa.Column("prizepicks_fantasy_points", sa.Double, nullable=True))


def downgrade() -> None:
    op.drop_column("nfl_player_weekly_stats", "prizepicks_fantasy_points")
    for column in reversed(_COUNT_COLUMNS):
        op.drop_column("nfl_player_weekly_stats", column)
