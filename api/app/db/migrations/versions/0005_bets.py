"""bets

Adds bets table for user bet tracking (daily P&L, settle results).

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bets",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "match_id",
            sa.BigInteger,
            sa.ForeignKey("matches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("bet_date", sa.Date, server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("bet_type", sa.Text, nullable=False),   # "single" | "parlay_leg" | "parlay"
        sa.Column("source", sa.Text, nullable=True),       # "bankroll_builder" | "manual"
        sa.Column("pick_side", sa.Text, nullable=True),    # "p1" | "p2" | "over" | "under"
        sa.Column("odds_american", sa.Integer, nullable=False),
        sa.Column("wager", sa.Numeric(10, 2), nullable=False),
        sa.Column("potential_payout", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.Text, server_default="pending", nullable=False),
        sa.Column("actual_payout", sa.Numeric(10, 2), nullable=True),
        sa.Column("parlay_id", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("idx_bets_date", "bets", ["bet_date"])
    op.create_index("idx_bets_match", "bets", ["match_id"])
    op.create_index("idx_bets_status", "bets", ["status"])
    op.execute(
        "CREATE INDEX idx_bets_parlay ON bets (parlay_id) WHERE parlay_id IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("idx_bets_parlay", table_name="bets")
    op.drop_index("idx_bets_status", table_name="bets")
    op.drop_index("idx_bets_match", table_name="bets")
    op.drop_index("idx_bets_date", table_name="bets")
    op.drop_table("bets")
