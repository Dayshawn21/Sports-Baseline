"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-03-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── players ──────────────────────────────────────────────────────────────
    op.create_table(
        "players",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("name_norm", sa.Text, nullable=False),
        sa.Column("tour", sa.Text, nullable=False),  # 'ATP' | 'WTA'
        sa.Column("sofascore_id", sa.Integer, nullable=True),
        sa.Column("ta_id", sa.Integer, nullable=True),
        sa.Column("birth_date", sa.Date, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_players_name_norm", "players", ["name_norm"], unique=True)

    # ── player_aliases ────────────────────────────────────────────────────────
    op.create_table(
        "player_aliases",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("canonical_player_id", sa.BigInteger, sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias_name", sa.Text, nullable=False),
        sa.Column("alias_name_norm", sa.Text, nullable=False),
        sa.Column("source", sa.Text, nullable=True),  # 'sofascore' | 'prizepicks' | 'manual'
    )
    op.create_index("idx_aliases_norm", "player_aliases", ["alias_name_norm"], unique=True)

    # ── matches ───────────────────────────────────────────────────────────────
    op.create_table(
        "matches",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("match_key", sa.Text, nullable=False),
        sa.Column("match_date", sa.Date, nullable=False),
        sa.Column("start_utc", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("tour", sa.Text, nullable=False),
        sa.Column("surface", sa.Text, nullable=True),
        sa.Column("tournament", sa.Text, nullable=True),
        sa.Column("round", sa.Text, nullable=True),
        sa.Column("best_of", sa.SmallInteger, nullable=True),
        sa.Column("p1_id", sa.BigInteger, sa.ForeignKey("players.id"), nullable=False),
        sa.Column("p2_id", sa.BigInteger, sa.ForeignKey("players.id"), nullable=False),
        sa.Column("p1_rank", sa.Integer, nullable=True),
        sa.Column("p2_rank", sa.Integer, nullable=True),
        sa.Column("winner_id", sa.BigInteger, sa.ForeignKey("players.id"), nullable=True),
        sa.Column("score", sa.Text, nullable=True),
        sa.Column("status", sa.Text, server_default="scheduled", nullable=False),
        sa.Column("sofascore_id", sa.Integer, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_matches_key", "matches", ["match_key"], unique=True)
    op.create_index("idx_matches_date", "matches", ["match_date"])
    op.create_index("idx_matches_status", "matches", ["status"])

    # ── match_odds ────────────────────────────────────────────────────────────
    op.create_table(
        "match_odds",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.BigInteger, sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("book", sa.Text, nullable=False),    # 'draftkings' | 'pinnacle' etc.
        sa.Column("market", sa.Text, nullable=False),  # 'moneyline' | 'total_games' | 'set1_winner'
        sa.Column("p1_odds", sa.Integer, nullable=True),
        sa.Column("p2_odds", sa.Integer, nullable=True),
        sa.Column("line", sa.Numeric(6, 1), nullable=True),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_match_odds_match", "match_odds", ["match_id", "market"])

    # ── player_elo ────────────────────────────────────────────────────────────
    op.create_table(
        "player_elo",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("player_id", sa.BigInteger, sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("as_of_date", sa.Date, nullable=False),
        sa.Column("elo", sa.Float, nullable=True),
        sa.Column("elo_hard", sa.Float, nullable=True),
        sa.Column("elo_clay", sa.Float, nullable=True),
        sa.Column("elo_grass", sa.Float, nullable=True),
        sa.Column("source", sa.Text, server_default="tennisabstract", nullable=True),
    )
    op.create_index("idx_player_elo_unique", "player_elo", ["player_id", "as_of_date"], unique=True)

    # ── player_rolling_stats ──────────────────────────────────────────────────
    op.create_table(
        "player_rolling_stats",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("player_id", sa.BigInteger, sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("surface", sa.Text, nullable=True),       # NULL = all surfaces
        sa.Column("window_matches", sa.Integer, nullable=True),  # 10, 20, etc.
        sa.Column("computed_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("win_rate", sa.Float, nullable=True),
        sa.Column("svc_pts_won", sa.Float, nullable=True),
        sa.Column("ret_pts_won", sa.Float, nullable=True),
        sa.Column("aces_per_game", sa.Float, nullable=True),
        sa.Column("df_per_game", sa.Float, nullable=True),
        sa.Column("hold_pct", sa.Float, nullable=True),
        sa.Column("break_pct", sa.Float, nullable=True),
        sa.Column("matches_count", sa.Integer, nullable=True),
    )
    op.create_index("idx_rolling_player", "player_rolling_stats", ["player_id", "surface", "window_matches"])

    # ── h2h ──────────────────────────────────────────────────────────────────
    op.create_table(
        "h2h",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("p1_id", sa.BigInteger, sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("p2_id", sa.BigInteger, sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("surface", sa.Text, nullable=True),  # NULL = all surfaces
        sa.Column("p1_wins", sa.Integer, server_default="0", nullable=False),
        sa.Column("p2_wins", sa.Integer, server_default="0", nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_h2h_unique", "h2h", ["p1_id", "p2_id", "surface"], unique=True)

    # ── predictions ───────────────────────────────────────────────────────────
    op.create_table(
        "predictions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.BigInteger, sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("model_version", sa.Text, nullable=False),
        sa.Column("p1_elo_prob", sa.Float, nullable=True),
        sa.Column("p1_ml_prob", sa.Float, nullable=True),
        sa.Column("p1_market_prob", sa.Float, nullable=True),
        sa.Column("p1_ensemble_prob", sa.Float, nullable=True),
        sa.Column("ensemble_weights", JSONB, nullable=True),
        sa.Column("quality_flags", sa.ARRAY(sa.Text), nullable=True),
        sa.Column("feature_snapshot", JSONB, nullable=True),
    )
    op.create_index("idx_predictions_match", "predictions", ["match_id", "generated_at"])

    # ── props ─────────────────────────────────────────────────────────────────
    op.create_table(
        "props",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("player_id", sa.BigInteger, sa.ForeignKey("players.id"), nullable=True),
        sa.Column("match_id", sa.BigInteger, sa.ForeignKey("matches.id"), nullable=True),
        sa.Column("source", sa.Text, nullable=False),     # 'prizepicks' | 'draftkings'
        sa.Column("stat_type", sa.Text, nullable=False),  # 'aces' | 'double_faults' | 'total_games' | 'break_points'
        sa.Column("line", sa.Numeric(6, 1), nullable=False),
        sa.Column("odds_type", sa.Text, nullable=True),   # 'standard' | 'goblin' | 'demon'
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("start_time", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("raw_json", JSONB, nullable=True),
    )
    op.create_index("idx_props_player_stat", "props", ["player_id", "stat_type", "fetched_at"])


def downgrade() -> None:
    op.drop_table("props")
    op.drop_table("predictions")
    op.drop_table("h2h")
    op.drop_table("player_rolling_stats")
    op.drop_table("player_elo")
    op.drop_table("match_odds")
    op.drop_table("matches")
    op.drop_table("player_aliases")
    op.drop_table("players")
