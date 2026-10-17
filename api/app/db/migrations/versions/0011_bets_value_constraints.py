"""bets value constraints

Adds CHECK constraints to the bets table so invalid financial records cannot be
written: non-positive wagers, negative payouts, and American odds inside the
(-100, 100) gap where no real price exists.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-13
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint("ck_bets_wager_positive", "bets", "wager > 0")
    op.create_check_constraint(
        "ck_bets_potential_payout_non_negative", "bets", "potential_payout >= 0"
    )
    op.create_check_constraint(
        "ck_bets_actual_payout_non_negative",
        "bets",
        "actual_payout IS NULL OR actual_payout >= 0",
    )
    op.create_check_constraint(
        "ck_bets_odds_american_valid", "bets", "odds_american <= -100 OR odds_american >= 100"
    )
    op.create_check_constraint(
        "ck_bets_status_valid",
        "bets",
        "status IN ('pending', 'won', 'lost', 'push', 'void')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_bets_status_valid", "bets", type_="check")
    op.drop_constraint("ck_bets_odds_american_valid", "bets", type_="check")
    op.drop_constraint("ck_bets_actual_payout_non_negative", "bets", type_="check")
    op.drop_constraint("ck_bets_potential_payout_non_negative", "bets", type_="check")
    op.drop_constraint("ck_bets_wager_positive", "bets", type_="check")
