"""rolling_stats_opp_allowed

Adds opponent-allowed fields to player_rolling_stats. These capture how players
perform defensively (i.e. what opponents achieve *against them*). Drives
matchup-aware prop projections that replace the previous league-average proxy.

Source: TennisAbstract per-match opponent columns (oaces, odfs, opts, ofirsts,
ofwon, oswon, ogames, osaved, ochances) aggregated over the same rolling window.

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("player_rolling_stats", sa.Column("allowed_aces_per_sp", sa.Numeric(7, 4), nullable=True))
    op.add_column("player_rolling_stats", sa.Column("allowed_df_per_sp", sa.Numeric(7, 4), nullable=True))
    op.add_column("player_rolling_stats", sa.Column("allowed_first_in_pct", sa.Numeric(7, 4), nullable=True))
    op.add_column("player_rolling_stats", sa.Column("allowed_first_won_pct", sa.Numeric(7, 4), nullable=True))
    op.add_column("player_rolling_stats", sa.Column("allowed_second_won_pct", sa.Numeric(7, 4), nullable=True))
    op.add_column("player_rolling_stats", sa.Column("allowed_hold_pct", sa.Numeric(7, 4), nullable=True))


def downgrade() -> None:
    op.drop_column("player_rolling_stats", "allowed_hold_pct")
    op.drop_column("player_rolling_stats", "allowed_second_won_pct")
    op.drop_column("player_rolling_stats", "allowed_first_won_pct")
    op.drop_column("player_rolling_stats", "allowed_first_in_pct")
    op.drop_column("player_rolling_stats", "allowed_df_per_sp")
    op.drop_column("player_rolling_stats", "allowed_aces_per_sp")
