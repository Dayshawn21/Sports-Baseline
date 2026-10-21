"""Immutable shadow forecast pairs and their coverage attempts.

Revision ID: 0047
Revises: 0046
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0047"
down_revision: str = "0046"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    op.create_table(
        "tennis_elo_freeze_cycles",
        sa.Column("experiment_version", sa.Text(), nullable=False),
        sa.Column("cycle_key", sa.DateTime(timezone=True), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("plan_sha256", sa.Text(), nullable=False),
        sa.Column("attempts", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("experiment_version", "cycle_key"),
        sa.CheckConstraint("experiment_version = 'tennis-elo-source-v1'", name="ck_elo_cycle_experiment"),
        sa.CheckConstraint("cycle_key <= frozen_at", name="ck_elo_cycle_time"),
        sa.CheckConstraint("plan_sha256 ~ '^[a-f0-9]{64}$'", name="ck_elo_cycle_hash"),
        sa.CheckConstraint("jsonb_typeof(attempts) = 'array'", name="ck_elo_cycle_attempts"),
    )
    op.create_table(
        "tennis_elo_comparisons",
        sa.Column("match_id", sa.BigInteger(), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("experiment_version", sa.Text(), nullable=False),
        sa.Column("cycle_key", sa.DateTime(timezone=True), nullable=False),
        sa.Column("p1_id", sa.BigInteger(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("p2_id", sa.BigInteger(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("comparison_group", sa.Text(), nullable=False),
        sa.Column("kickoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("match_id", "experiment_version"),
        sa.ForeignKeyConstraint(
            ["experiment_version", "cycle_key"],
            ["tennis_elo_freeze_cycles.experiment_version", "tennis_elo_freeze_cycles.cycle_key"],
        ),
        sa.CheckConstraint("p1_id <> p2_id", name="ck_elo_pair_players"),
        sa.CheckConstraint("cycle_key <= frozen_at AND frozen_at < kickoff", name="ck_elo_pair_time"),
        sa.CheckConstraint("comparison_group IN ('ATP','WTA','ATP_CHALLENGER')", name="ck_elo_pair_group"),
        sa.CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_elo_pair_payload"),
    )


def downgrade() -> None:
    op.drop_table("tennis_elo_comparisons")
    op.drop_table("tennis_elo_freeze_cycles")
