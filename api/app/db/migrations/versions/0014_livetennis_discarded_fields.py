"""livetennisapi fields the ingest was discarding

Every /matches response already carries these; the ingest parsed only id, name,
ranking, and birthday and dropped the rest. No new API calls are involved.

Ranking snapshots go on `matches` beside p1_rank/p2_rank rather than on
`players`, because a ranking is a point-in-time value. Storing it per match is
what lets it become an honest training feature later; a current-value column on
`players` would leak the future into past rows.

`hand` and `country` go on `players` because they do not change per match.

`tournament_id` is text, not an integer: the provider sends it quoted ("11043").

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, Sequence[str], None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MATCH_COLUMNS = (
    sa.Column("indoor", sa.Boolean(), nullable=True),
    sa.Column("tournament_id", sa.Text(), nullable=True),
    sa.Column("p1_ranking_points", sa.Integer(), nullable=True),
    sa.Column("p2_ranking_points", sa.Integer(), nullable=True),
    sa.Column("p1_ranking_movement", sa.Text(), nullable=True),
    sa.Column("p2_ranking_movement", sa.Text(), nullable=True),
)

PLAYER_COLUMNS = (
    sa.Column("hand", sa.Text(), nullable=True),
    sa.Column("country", sa.Text(), nullable=True),
)


def upgrade() -> None:
    for column in MATCH_COLUMNS:
        op.add_column("matches", column)
    for column in PLAYER_COLUMNS:
        op.add_column("players", column)


def downgrade() -> None:
    for column in PLAYER_COLUMNS:
        op.drop_column("players", column.name)
    for column in MATCH_COLUMNS:
        op.drop_column("matches", column.name)
