"""Map provider player names to NFL players.

Deliberately mirrors the tennis `player_aliases` shape so item 17 can converge
the two rather than reconcile two different designs.

The automatic pass cannot resolve every name: NFLverse stores first-initial plus
surname, which collides (three `J.Williams`), and provider-only players such as
rookies have no row to match at all. This table holds the decisions a human or a
later linking pass makes, and is the override when automatic matching is wrong.

Revision ID: 0018
Revises: 0017
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, Sequence[str], None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nfl_player_aliases",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "nfl_player_id",
            sa.BigInteger,
            sa.ForeignKey("nfl_players.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias_name", sa.Text, nullable=False),
        sa.Column("alias_name_norm", sa.Text, nullable=False),
        sa.Column("source", sa.Text, nullable=True),  # 'prizepicks' | 'manual'
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Unique so one provider name can never point at two players; that ambiguity
    # is what the alias table exists to resolve.
    op.create_index("idx_nfl_aliases_norm", "nfl_player_aliases", ["alias_name_norm"], unique=True)
    op.create_index("idx_nfl_aliases_player", "nfl_player_aliases", ["nfl_player_id"])


def downgrade() -> None:
    op.drop_index("idx_nfl_aliases_player", table_name="nfl_player_aliases")
    op.drop_index("idx_nfl_aliases_norm", table_name="nfl_player_aliases")
    op.drop_table("nfl_player_aliases")
