"""The grading loader must never see the future: the prediction is from before the
start, the opening price from before the prediction, and the close from the same
book before the start."""
import asyncio
from datetime import datetime, timezone
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.repositories.predictions import build_graded_prediction, get_graded_predictions


class _Result:
    def mappings(self):
        return self

    def all(self) -> list:
        return []


class _RecordingSession:
    statement = ""

    async def execute(self, statement: TextClause, params: dict | None = None) -> _Result:
        self.statement = " ".join(str(statement).split())
        return _Result()


@pytest.fixture(scope="module")
def sql() -> str:
    session = _RecordingSession()
    asyncio.run(get_graded_predictions(cast(AsyncSession, session)))
    return session.statement


class TestNoLookahead:
    def test_the_prediction_is_strictly_before_the_start(self, sql):
        assert "generated_at < m.start_utc" in sql
        assert "ORDER BY generated_at DESC, id DESC LIMIT 1" in sql

    def test_the_opening_price_is_no_later_than_the_prediction(self, sql):
        opening = sql.split("LATERAL (")[2]
        assert "fetched_at <= p.generated_at" in opening
        assert opening.index("fetched_at DESC") < opening.index("CASE LOWER(book)")

    def test_the_close_is_the_same_book_before_the_start(self, sql):
        closing = sql.split("LATERAL (")[3]
        assert "fetched_at <= m.start_utc" in closing
        assert "= CASE WHEN LOWER(op.book)" in closing

    def test_only_settled_matches_with_a_start_time(self, sql):
        assert "m.status = 'completed' AND m.winner_id IS NOT NULL AND m.start_utc IS NOT NULL" in sql


def _row(**over) -> dict:
    row = {
        "match_id": 7, "tour": "ATP",
        "start_utc": datetime(2026, 9, 20, 18, tzinfo=timezone.utc),
        "generated_at": datetime(2026, 9, 20, 13, 30, tzinfo=timezone.utc),
        "model_version": "ensemble-v1+lgbm-v6", "p1_won": True,
        "score": "6-4 6-3", "best_of": 3,
        "elo_prob": 0.6, "ml_prob": 0.62, "ensemble_prob": 0.61,
        "market_book": "draftkings",
        "open_p1_odds": -150, "open_p2_odds": 130,
        "close_p1_odds": -200, "close_p2_odds": 170,
    }
    row.update(over)
    return row


class TestBuildGradedPrediction:
    def test_prices_are_de_vigged_for_p1(self):
        graded = build_graded_prediction(_row())
        assert graded.market_prob == pytest.approx(0.6 / (0.6 + 100 / 230))
        assert graded.closing_market_prob > graded.market_prob

    def test_either_side_can_have_won(self):
        assert build_graded_prediction(_row()).p1_won is True
        assert build_graded_prediction(_row(p1_won=False)).p1_won is False

    def test_a_missing_close_is_none_not_zero(self):
        assert build_graded_prediction(_row(close_p1_odds=None, close_p2_odds=None)).closing_market_prob is None

    def test_a_retirement_is_marked_incomplete(self):
        assert build_graded_prediction(_row(score="6-4 3-2")).completed_score is False

    def test_a_missing_best_of_is_read_as_three(self):
        assert build_graded_prediction(_row(best_of=None)).completed_score is True
