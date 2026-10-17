"""Add ESPN's stable event id for immutable completed-game summary caching."""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, Sequence[str], None] = "0015"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("nfl_games", sa.Column("espn_event_id", sa.Text(), nullable=True))
    op.create_index("idx_nfl_games_espn_event", "nfl_games", ["espn_event_id"], unique=True)

def downgrade() -> None:
    op.drop_index("idx_nfl_games_espn_event", table_name="nfl_games")
    op.drop_column("nfl_games", "espn_event_id")
