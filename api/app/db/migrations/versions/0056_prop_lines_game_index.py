"""Index `sport_prop_lines` by game.

Every game-scoped prop read seq-scanned the whole table: the NHL slate's prop
count read 1.1 GB of all sports' rows to keep 4,187 (7.27 s cold, 2026-11-23).
Built concurrently so the snapshot writers are never blocked.

Revision ID: 0056
Revises: 0055
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0056"
down_revision: Union[str, Sequence[str], None] = "0055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sport_prop_lines_game ON sport_prop_lines (game_id)")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_sport_prop_lines_game")
