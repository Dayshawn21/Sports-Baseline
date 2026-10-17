"""Persist timestamped forecast snapshots for NFL games.

Revision ID: 0022
Revises: 0021
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0022"
down_revision: Union[str, Sequence[str], None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nfl_game_weather_snapshots",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("game_id", sa.BigInteger, sa.ForeignKey("nfl_games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("venue_type", sa.Text, nullable=False),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column("forecast_for", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("temperature_f", sa.Numeric(5, 1), nullable=True),
        sa.Column("wind_mph", sa.Numeric(5, 1), nullable=True),
        sa.Column("wind_gust_mph", sa.Numeric(5, 1), nullable=True),
        sa.Column("precipitation_probability", sa.Numeric(5, 1), nullable=True),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("raw_json", JSONB, nullable=True),
        sa.CheckConstraint("venue_type IN ('outdoor', 'dome', 'retractable')", name="ck_nfl_weather_venue_type"),
    )
    op.create_index("idx_nfl_game_weather_latest", "nfl_game_weather_snapshots", ["game_id", "fetched_at"])


def downgrade() -> None:
    op.drop_index("idx_nfl_game_weather_latest", table_name="nfl_game_weather_snapshots")
    op.drop_table("nfl_game_weather_snapshots")
