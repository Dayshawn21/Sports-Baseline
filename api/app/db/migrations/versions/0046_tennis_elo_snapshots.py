"""Isolated candidate ELO ratings for the 41b forward comparison.

Revision ID: 0046
Revises: 0045
"""
from alembic import op
import sqlalchemy as sa

revision: str = "0046"
down_revision: str = "0045"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    op.create_table(
        "tennis_elo_snapshots",
        sa.Column("player_id", sa.BigInteger(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("overall", sa.Float(), nullable=False),
        sa.Column("hard", sa.Float(), nullable=True),
        sa.Column("clay", sa.Float(), nullable=True),
        sa.Column("grass", sa.Float(), nullable=True),
        sa.Column("overall_matches", sa.Integer(), nullable=False),
        sa.Column("hard_matches", sa.Integer(), nullable=False),
        sa.Column("clay_matches", sa.Integer(), nullable=False),
        sa.Column("grass_matches", sa.Integer(), nullable=False),
        sa.Column("provider_namespace", sa.Text(), nullable=False),
        sa.Column("provider_player_id", sa.Text(), nullable=False),
        sa.Column("computed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("source_downloaded_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("replay_cutoff", sa.Date(), nullable=False),
        sa.Column("method_version", sa.Text(), nullable=False),
        sa.Column("manifest_sha256", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("player_id", "source", "as_of_date", name="pk_tennis_elo_snapshots"),
        sa.UniqueConstraint("source", "as_of_date", "provider_namespace", "provider_player_id",
                            name="uq_tennis_elo_snapshots_provider"),
        sa.CheckConstraint("btrim(source) <> '' AND btrim(method_version) <> ''", name="ck_tennis_elo_version"),
        sa.CheckConstraint("provider_namespace IN ('ATP', 'WTA') AND provider_player_id ~ '^[A-Za-z0-9]+$'",
                           name="ck_tennis_elo_provider"),
        sa.CheckConstraint("manifest_sha256 ~ '^[a-f0-9]{64}$'", name="ck_tennis_elo_manifest"),
        sa.CheckConstraint("source_downloaded_at <= computed_at AND replay_cutoff = as_of_date "
                           "AND as_of_date = (computed_at AT TIME ZONE 'UTC')::date", name="ck_tennis_elo_dates"),
        sa.CheckConstraint("overall_matches > 0 AND hard_matches >= 0 AND clay_matches >= 0 AND grass_matches >= 0 "
                           "AND hard_matches + clay_matches + grass_matches <= overall_matches",
                           name="ck_tennis_elo_counts"),
        sa.CheckConstraint("overall > '-Infinity'::float8 AND overall < 'Infinity'::float8",
                           name="ck_tennis_elo_overall"),
        *[
            sa.CheckConstraint(
                f"({surface} IS NULL AND {surface}_matches = 0) OR "
                f"({surface} IS NOT NULL AND {surface}_matches > 0 "
                f"AND {surface} > '-Infinity'::float8 AND {surface} < 'Infinity'::float8)",
                name=f"ck_tennis_elo_{surface}",
            ) for surface in ("hard", "clay", "grass")
        ],
    )


def downgrade() -> None:
    op.drop_table("tennis_elo_snapshots")
