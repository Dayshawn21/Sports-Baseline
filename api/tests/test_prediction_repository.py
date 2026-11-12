import asyncio
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.repositories.predictions import insert_prediction, insert_prediction_shadow


class _Result:
    def scalar_one(self) -> int:
        return 7


class _RecordingSession:
    def __init__(self) -> None:
        self.statement = ""
        self.params: dict[str, object] = {}

    async def execute(
        self,
        statement: TextClause,
        params: dict[str, object],
    ) -> _Result:
        self.statement = str(statement)
        self.params = params
        return _Result()


def test_insert_prediction_serializes_jsonb_parameters() -> None:
    session = _RecordingSession()

    prediction_id = asyncio.run(
        insert_prediction(
            cast(AsyncSession, session),
            match_id=42,
            model_version="ensemble-v1+lgbm-v5",
            p1_elo_prob=0.60,
            p1_ml_prob=0.65,
            p1_market_prob=0.58,
            p1_ensemble_prob=0.63,
            ensemble_weights={"elo": 0.35, "ml": 0.40, "market": 0.25},
            quality_flags=["stale_odds"],
            feature_snapshot={"surface": "Hard"},
        )
    )

    assert prediction_id == 7
    assert session.params["weights"] == '{"elo": 0.35, "ml": 0.4, "market": 0.25}'
    assert session.params["snap"] == '{"surface": "Hard"}'
    assert session.params["flags"] == ["stale_odds"]
    assert "CAST(:weights AS jsonb)" in session.statement
    assert "CAST(:snap AS jsonb)" in session.statement


def test_insert_prediction_shadow_writes_only_the_shadow_table() -> None:
    session = _RecordingSession()

    asyncio.run(insert_prediction_shadow(
        cast(AsyncSession, session), prediction_id=7,
        model_version="ensemble-v3+lgbm-v6+shrink-v1", p1_prob=0.615,
    ))

    statement = " ".join(session.statement.split())
    assert statement == (
        "INSERT INTO prediction_shadows (prediction_id, model_version, p1_prob) VALUES (:pid, :mv, :p)"
    )
    assert session.params == {"pid": 7, "mv": "ensemble-v3+lgbm-v6+shrink-v1", "p": 0.615}
