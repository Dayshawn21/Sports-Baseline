"""Re-running the snapshot job must never duplicate or overwrite a stored prediction."""
import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.repositories.prop_snapshots import (
    build_graded_prop_snapshot,
    get_graded_prop_snapshots,
    insert_prop_projection_snapshots,
)
from app.services.tennis.prop_snapshots import PROJECTION_VERSION, PropProjectionSnapshot

START = datetime(2026, 9, 25, 18, 30, tzinfo=timezone.utc)


def _snapshot(prop_id: int = 7) -> PropProjectionSnapshot:
    return PropProjectionSnapshot(
        prop_id=prop_id, projection_version=PROJECTION_VERSION, player_id=11, match_id=21,
        stat_type="Total Games", odds_type="standard", line=21.5, start_time=START,
        recommendation="UNDER", confidence="LEAN", hit_probability=0.56, p_over=0.44, p_under=0.56,
        p_push=0.0, stat_avg=20.9, ev_pct=-3.0, break_even_pct=57.7, matches_count=18,
        market_total_games=21.5, projection_status="ok", data_quality_flags=["small_sample"],
        projection_inputs={"projection_source": "market_total"},
    )


class _Result:
    def fetchall(self) -> list:
        return [(1,), (2,)]


class _RecordingSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, statement: TextClause, params: dict | None = None) -> _Result:
        self.calls.append((" ".join(str(statement).split()), params or {}))
        return _Result()


def _insert(snapshots: list[PropProjectionSnapshot]) -> tuple[int, _RecordingSession]:
    session = _RecordingSession()
    inserted = asyncio.run(insert_prop_projection_snapshots(cast(AsyncSession, session), snapshots))
    return inserted, session


def test_an_existing_prop_and_version_is_left_alone():
    _, session = _insert([_snapshot()])
    sql, _ = session.calls[0]
    assert "ON CONFLICT (prop_id, projection_version) DO NOTHING" in sql
    assert "RETURNING id" in sql


def test_the_batch_is_one_statement_with_typed_array_and_json_columns():
    inserted, session = _insert([_snapshot(1), _snapshot(2)])
    assert len(session.calls) == 1 and inserted == 2
    sql, params = session.calls[0]
    assert "data_quality_flags text[]" in sql and "projection_inputs jsonb" in sql
    rows = json.loads(params["rows"])
    assert [r["prop_id"] for r in rows] == [1, 2]
    assert rows[0]["data_quality_flags"] == ["small_sample"]
    assert rows[0]["projection_inputs"] == {"projection_source": "market_total"}
    assert rows[0]["start_time"] == "2026-09-25 18:30:00+00:00"


def test_an_empty_batch_runs_no_query():
    inserted, session = _insert([])
    assert inserted == 0 and session.calls == []


class _GradedResult:
    def mappings(self):
        return self

    def all(self) -> list:
        return []


class _GradedSession(_RecordingSession):
    async def execute(self, statement: TextClause, params: dict | None = None) -> _GradedResult:
        self.calls.append((" ".join(str(statement).split()), params or {}))
        return _GradedResult()


@pytest.fixture(scope="module")
def graded_call() -> tuple[str, dict]:
    session = _GradedSession()
    asyncio.run(get_graded_prop_snapshots(cast(AsyncSession, session), PROJECTION_VERSION))
    return session.calls[0]


class TestGradedLoader:
    def test_only_one_projection_version_is_graded(self, graded_call):
        sql, params = graded_call
        assert "s.projection_version = :version" in sql
        assert params == {"version": PROJECTION_VERSION}

    def test_the_pair_is_returned_for_the_box_score_join(self, graded_call):
        sql, _ = graded_call
        assert "s.id AS snapshot_id, s.player_id, s.match_id, m.tour" in sql

    def test_the_latest_snapshot_per_line_wins(self, graded_call):
        sql, _ = graded_call
        key = "s.player_id, s.match_id, s.stat_type, COALESCE(s.odds_type, ''), s.line"
        assert f"SELECT DISTINCT ON ({key})" in sql
        assert f"ORDER BY {key}, s.snapshot_at DESC, s.id DESC" in sql

    def test_only_finished_matches_with_the_player_on_a_side(self, graded_call):
        sql, _ = graded_call
        assert "JOIN matches m ON m.id = s.match_id" in sql
        assert "m.status = 'completed' AND m.winner_id IS NOT NULL" in sql
        assert "s.player_id IN (m.p1_id, m.p2_id)" in sql

    def test_a_snapshot_taken_after_the_start_is_never_graded(self, graded_call):
        sql, _ = graded_call
        assert "s.snapshot_at < s.start_time" in sql


def test_graded_mapper_turns_the_numeric_line_into_a_float():
    row = build_graded_prop_snapshot({
        "snapshot_id": 1, "player_id": 11, "match_id": 21, "tour": "WTA", "stat_type": "Total Games", "odds_type": "standard",
        "line": Decimal("21.5"), "recommendation": "UNDER", "confidence": "LEAN", "hit_probability": 0.56,
        "player_is_p1": False, "score": "6-4 6-3", "best_of": 3,
    })
    assert row.line == 21.5 and isinstance(row.line, float)
    assert (row.player_id, row.match_id) == (11, 21)
