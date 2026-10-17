"""player_ta_slug

Adds ta_slug column to players table for custom TennisAbstract slug overrides.
When set, this overrides the default slug computed from the player's name.

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("players", sa.Column("ta_slug", sa.VARCHAR(200), nullable=True))


def downgrade() -> None:
    op.drop_column("players", "ta_slug")
