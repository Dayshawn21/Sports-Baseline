"""livetennisapi provider ids

Adds nullable `livetennis_id` to `players` and `matches` so rows can be tied back
to livetennisapi.com, which replaces the Sofascore scraper as the match/fixture
source.

Unlike `sofascore_id` (which has no unique constraint, and so allowed the
duplicate players that find_dupes.py/fix_dupes.py exist to clean up), both new
columns get a unique index. NULLs are distinct in Postgres, so the many rows
without a livetennis id are unaffected.

Existing `sofascore_id` columns are left in place — old rows keep them as history.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, Sequence[str], None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("players", sa.Column("livetennis_id", sa.Integer(), nullable=True))
    op.add_column("matches", sa.Column("livetennis_id", sa.Integer(), nullable=True))
    op.create_index(
        "idx_players_livetennis_id", "players", ["livetennis_id"], unique=True
    )
    op.create_index(
        "idx_matches_livetennis_id", "matches", ["livetennis_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("idx_matches_livetennis_id", table_name="matches")
    op.drop_index("idx_players_livetennis_id", table_name="players")
    op.drop_column("matches", "livetennis_id")
    op.drop_column("players", "livetennis_id")
