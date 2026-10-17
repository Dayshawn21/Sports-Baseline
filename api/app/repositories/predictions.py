from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.odds import implied_prob_from_american
from app.core.tennis_grading import is_completed_score
from app.repositories.matches import _BOOK_PRIORITY_SQL


@dataclass
class Prediction:
    id: int
    match_id: int
    generated_at: datetime
    model_version: str
    p1_elo_prob: Optional[float]
    p1_ml_prob: Optional[float]
    p1_market_prob: Optional[float]
    p1_ensemble_prob: Optional[float]


async def insert_prediction(
    db: AsyncSession,
    match_id: int,
    model_version: str,
    p1_elo_prob: Optional[float],
    p1_ml_prob: Optional[float],
    p1_market_prob: Optional[float],
    p1_ensemble_prob: Optional[float],
    ensemble_weights: Optional[dict] = None,
    quality_flags: Optional[list[str]] = None,
    feature_snapshot: Optional[dict] = None,
) -> int:
    row = await db.execute(
        text("""
            INSERT INTO predictions
              (match_id, model_version, p1_elo_prob, p1_ml_prob, p1_market_prob,
               p1_ensemble_prob, ensemble_weights, quality_flags, feature_snapshot)
            VALUES
              (:mid, :mv, :elo, :ml, :mkt, :ens,
               CAST(:weights AS jsonb), :flags, CAST(:snap AS jsonb))
            RETURNING id
        """),
        {
            "mid": match_id, "mv": model_version,
            "elo": p1_elo_prob, "ml": p1_ml_prob, "mkt": p1_market_prob, "ens": p1_ensemble_prob,
            "weights": json.dumps(ensemble_weights) if ensemble_weights is not None else None,
            "flags": quality_flags,
            "snap": json.dumps(feature_snapshot) if feature_snapshot is not None else None,
        },
    )
    return row.scalar_one()


async def get_latest_prediction(db: AsyncSession, match_id: int) -> Optional[Prediction]:
    row = await db.execute(
        text("""
            SELECT id, match_id, generated_at, model_version,
                   p1_elo_prob, p1_ml_prob, p1_market_prob, p1_ensemble_prob
            FROM predictions
            WHERE match_id = :mid
            ORDER BY generated_at DESC
            LIMIT 1
        """),
        {"mid": match_id},
    )
    r = row.fetchone()
    return Prediction(*r) if r else None


@dataclass(frozen=True)
class StoredPrediction:
    """A match's last prediction made before it started, with the moneyline it saw."""
    generated_at: datetime
    model_version: str
    p1_elo_prob: Optional[float]
    p1_ml_prob: Optional[float]
    p1_market_prob: Optional[float]
    p1_ensemble_prob: Optional[float]
    ensemble_weights: dict[str, float]
    quality_flags: list[str]
    p1_odds: Optional[int]
    p2_odds: Optional[int]


async def get_prestart_prediction(
    db: AsyncSession, match_id: int, start_utc: datetime
) -> Optional[StoredPrediction]:
    # The price is the one the prediction saw (as 26a pairs them), not the
    # close: an edge mixing a stored model number with a later price is neither.
    row = await db.execute(
        text("""
            SELECT p.generated_at, p.model_version,
                   p.p1_elo_prob, p.p1_ml_prob, p.p1_market_prob, p.p1_ensemble_prob,
                   p.ensemble_weights, p.quality_flags, op.p1_odds, op.p2_odds
            FROM (
                SELECT *
                FROM predictions
                WHERE match_id = :mid AND generated_at < :start
                ORDER BY generated_at DESC, id DESC
                LIMIT 1
            ) p
            LEFT JOIN LATERAL (
                SELECT p1_odds, p2_odds
                FROM match_odds
                WHERE match_id = :mid AND market = 'moneyline'
                  AND p1_odds IS NOT NULL AND p2_odds IS NOT NULL
                  AND fetched_at <= p.generated_at
                ORDER BY fetched_at DESC, """ + _BOOK_PRIORITY_SQL + """
                LIMIT 1
            ) op ON true
        """),
        {"mid": match_id, "start": start_utc},
    )
    r = row.fetchone()
    if r is None:
        return None
    return StoredPrediction(
        generated_at=r[0], model_version=r[1],
        p1_elo_prob=r[2], p1_ml_prob=r[3], p1_market_prob=r[4], p1_ensemble_prob=r[5],
        ensemble_weights=r[6] or {}, quality_flags=list(r[7] or []),
        p1_odds=r[8], p2_odds=r[9],
    )


@dataclass(frozen=True)
class GradedPrediction:
    """One settled match, its last pre-start prediction, and the market around it.

    Load-bearing: 26c scores historical rows through the same shape and 26d fits
    on it. Every probability is for p1.
    """
    match_id: int
    tour: str
    start_utc: datetime
    generated_at: datetime
    model_version: str
    p1_won: bool
    completed_score: bool
    elo_prob: Optional[float]
    ml_prob: Optional[float]
    market_prob: Optional[float]
    ensemble_prob: Optional[float]
    market_book: Optional[str]
    closing_market_prob: Optional[float]


def _devig(p1_odds: Optional[int], p2_odds: Optional[int]) -> Optional[float]:
    if not p1_odds or not p2_odds:
        return None
    return implied_prob_from_american(p1_odds, p2_odds)[0]


def build_graded_prediction(row: dict) -> GradedPrediction:
    return GradedPrediction(
        match_id=row["match_id"],
        tour=row["tour"],
        start_utc=row["start_utc"],
        generated_at=row["generated_at"],
        model_version=row["model_version"],
        p1_won=bool(row["p1_won"]),
        completed_score=is_completed_score(row["score"], row["best_of"] or 3),
        elo_prob=row["elo_prob"],
        ml_prob=row["ml_prob"],
        market_prob=_devig(row["open_p1_odds"], row["open_p2_odds"]),
        ensemble_prob=row["ensemble_prob"],
        market_book=row["market_book"],
        closing_market_prob=_devig(row["close_p1_odds"], row["close_p2_odds"]),
    )


# Bet365 was stored as betonline.ag until 2026-09-25; a price that changed name
# between the prediction and the start is still the same book.
_SAME_BOOK_KEY = "CASE WHEN LOWER({col}) IN ('betonline.ag', 'betonline') THEN 'bet365' ELSE LOWER({col}) END"


async def get_graded_predictions(db: AsyncSession) -> list[GradedPrediction]:
    """Every settled match with a prediction made before it started.

    The market price at prediction time is re-read from match_odds rather than
    taken from predictions.p1_market_prob: that stored value came from whichever
    book won an arbitrary same-run tie, and a closing price from another book
    would then record a book switch as a market move. Both prices here come from
    one book.
    """
    rows = await db.execute(
        text("""
            SELECT
                m.id AS match_id, m.tour, m.start_utc, m.score, m.best_of,
                (m.winner_id = m.p1_id) AS p1_won,
                p.generated_at, p.model_version,
                p.p1_elo_prob AS elo_prob, p.p1_ml_prob AS ml_prob, p.p1_ensemble_prob AS ensemble_prob,
                op.book AS market_book, op.p1_odds AS open_p1_odds, op.p2_odds AS open_p2_odds,
                cl.p1_odds AS close_p1_odds, cl.p2_odds AS close_p2_odds
            FROM matches m
            JOIN LATERAL (
                SELECT generated_at, model_version, p1_elo_prob, p1_ml_prob, p1_ensemble_prob
                FROM predictions
                WHERE match_id = m.id AND generated_at < m.start_utc
                ORDER BY generated_at DESC, id DESC
                LIMIT 1
            ) p ON true
            LEFT JOIN LATERAL (
                SELECT book, p1_odds, p2_odds
                FROM match_odds
                WHERE match_id = m.id AND market = 'moneyline'
                  AND p1_odds IS NOT NULL AND p2_odds IS NOT NULL
                  AND fetched_at <= p.generated_at
                ORDER BY fetched_at DESC, """ + _BOOK_PRIORITY_SQL + """
                LIMIT 1
            ) op ON true
            LEFT JOIN LATERAL (
                SELECT p1_odds, p2_odds
                FROM match_odds
                WHERE match_id = m.id AND market = 'moneyline'
                  AND p1_odds IS NOT NULL AND p2_odds IS NOT NULL
                  AND fetched_at <= m.start_utc
                  AND """ + _SAME_BOOK_KEY.format(col="book") + " = " + _SAME_BOOK_KEY.format(col="op.book") + """
                ORDER BY fetched_at DESC
                LIMIT 1
            ) cl ON true
            WHERE m.status = 'completed' AND m.winner_id IS NOT NULL AND m.start_utc IS NOT NULL
            ORDER BY m.start_utc
        """)
    )
    return [build_graded_prediction(dict(r)) for r in rows.mappings().all()]
