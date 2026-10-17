"""Store each pre-match PrizePicks projection as the props page computed it.

Projections, hit probabilities and confidence tiers are computed on page load
from rolling stats that are overwritten in place, so a past tier cannot be
graded without leaking the result. These rows freeze them before the start.

Revision ID: 0034
Revises: 0033
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "0034"
down_revision: Union[str, Sequence[str], None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prop_projection_snapshots",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("prop_id", sa.BigInteger, sa.ForeignKey("props.id", ondelete="CASCADE"), nullable=False),
        sa.Column("projection_version", sa.Text, nullable=False),
        sa.Column("snapshot_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("player_id", sa.BigInteger, sa.ForeignKey("players.id"), nullable=False),
        # The match the page projected against, after its relink; can differ from props.match_id.
        sa.Column("match_id", sa.BigInteger, sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("stat_type", sa.Text, nullable=False),
        sa.Column("odds_type", sa.Text, nullable=True),
        sa.Column("line", sa.Numeric(6, 1), nullable=False),
        sa.Column("start_time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("recommendation", sa.Text, nullable=True),
        sa.Column("confidence", sa.Text, nullable=True),
        sa.Column("hit_probability", sa.Float, nullable=True),
        sa.Column("p_over", sa.Float, nullable=True),
        sa.Column("p_under", sa.Float, nullable=True),
        sa.Column("p_push", sa.Float, nullable=True),
        sa.Column("stat_avg", sa.Float, nullable=True),
        sa.Column("ev_pct", sa.Float, nullable=True),
        sa.Column("break_even_pct", sa.Float, nullable=True),
        sa.Column("matches_count", sa.Integer, nullable=True),
        sa.Column("market_total_games", sa.Float, nullable=True),
        sa.Column("projection_status", sa.Text, nullable=False),
        sa.Column("data_quality_flags", ARRAY(sa.Text), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("projection_inputs", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.UniqueConstraint("prop_id", "projection_version", name="uq_prop_projection_snapshots_prop_version"),
    )
    op.create_index("ix_prop_projection_snapshots_match", "prop_projection_snapshots", ["match_id"])


def downgrade() -> None:
    op.drop_index("ix_prop_projection_snapshots_match", table_name="prop_projection_snapshots")
    op.drop_table("prop_projection_snapshots")
