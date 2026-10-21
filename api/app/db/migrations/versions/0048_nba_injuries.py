"""Store complete ESPN NBA injury snapshots, including empty reports.

Revision ID: 0048
Revises: 0047
"""
from alembic import op
import sqlalchemy as sa

revision: str = "0048"
down_revision: str = "0047"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    op.create_table(
        "nba_injury_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, unique=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("source = 'ESPN'", name="ck_nba_injury_source"),
        sa.CheckConstraint("entry_count >= 0", name="ck_nba_injury_count"),
    )
    op.create_table(
        "nba_player_injuries",
        sa.Column("snapshot_id", sa.BigInteger(), sa.ForeignKey("nba_injury_snapshots.id"), nullable=False),
        sa.Column("espn_team_id", sa.Text(), nullable=False),
        sa.Column("team_code", sa.String(8), nullable=False),
        sa.Column("espn_athlete_id", sa.Text(), nullable=False),
        sa.Column("player_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("return_date", sa.Text(), nullable=True),
        sa.Column("athlete_team_id", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("snapshot_id", "espn_team_id", "espn_athlete_id"),
    )


def downgrade() -> None:
    op.drop_table("nba_player_injuries")
    op.drop_table("nba_injury_snapshots")
