"""Keep the TennisAbstract fields that tie a box score to one match.

Rows are dated by tournament start, so a player's several matches in one event
share a date and could not be told apart. Opponent, round and score can.
NULL means the row was ingested before this revision, not that the source lacked it.

Revision ID: 0035
Revises: 0034
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: Union[str, Sequence[str], None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = ("opponent_name", "round", "tournament", "score")


def upgrade() -> None:
    for column in _COLUMNS:
        op.add_column("player_match_stats", sa.Column(column, sa.Text, nullable=True))


def downgrade() -> None:
    for column in reversed(_COLUMNS):
        op.drop_column("player_match_stats", column)
