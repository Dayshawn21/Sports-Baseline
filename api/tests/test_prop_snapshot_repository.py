"""Re-running the snapshot job must never duplicate or overwrite a stored prediction."""
import asyncio
import json
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.repositories.prop_snapshots import (
    build_graded_prop_snapshot,
    build_prop_check_snapshot,
    get_graded_prop_snapshots,
    get_prop_check_snapshots,
    insert_prop_projection_snapshots,
    SnapshotInsertCounts,
)
from app.services.tennis.prop_snapshots import PROJECTION_VERSION, SNAPSHOT_ELIGIBILITY_POLICY, PropProjectionSnapshot

START = datetime(2026, 9, 25, 18, 30, tzinfo=timezone.utc)
CAPTURE = datetime(2026, 9, 25, 13, 30, tzinfo=timezone.utc)


def _snapshot(prop_id: int = 7) -> PropProjectionSnapshot:
    return PropProjectionSnapshot(
        prop_id=prop_id, projection_version=PROJECTION_VERSION, player_id=11, match_id=21,
        stat_type="Total Games", odds_type="standard", line=21.5, start_time=START,
        recommendation="UNDER", confidence="LEAN", hit_probability=0.56, p_over=0.44, p_under=0.56,
        p_push=0.0, stat_avg=20.9, ev_pct=-3.0, break_even_pct=57.7, matches_count=18,
        market_total_games=21.5, projection_status="ok", data_quality_flags=["small_sample"],
        projection_inputs={
            "projection_source": "market_total",
            "snapshot_eligibility_policy": SNAPSHOT_ELIGIBILITY_POLICY,
            "source_start_time": START.isoformat(),
            "match_start_time": START.isoformat(),
            "match_status_at_capture": "scheduled",
        },
        snapshot_at=CAPTURE,
    )


class _Result:
    def __init__(self, counts: SnapshotInsertCounts) -> None:
        self.counts = counts

    def mappings(self):
        return self

    def one(self) -> dict[str, int]:
        return asdict(self.counts)


class _RecordingSession:
    def __init__(self, counts: SnapshotInsertCounts | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.counts = counts

    async def execute(self, statement: TextClause, params: dict | None = None) -> _Result:
        self.calls.append((" ".join(str(statement).split()), params or {}))
        counts = self.counts or SnapshotInsertCounts(inserted=len(json.loads(params["rows"])))
        return _Result(counts)


def _insert(
    snapshots: list[PropProjectionSnapshot], counts: SnapshotInsertCounts | None = None,
) -> tuple[SnapshotInsertCounts, _RecordingSession]:
    session = _RecordingSession(counts)
    inserted = asyncio.run(insert_prop_projection_snapshots(cast(AsyncSession, session), snapshots))
    return inserted, session


def test_an_existing_prop_and_version_is_left_alone():
    _, session = _insert([_snapshot()])
    sql, _ = session.calls[0]
    assert "ON CONFLICT (prop_id, projection_version) DO NOTHING" in sql
    assert "RETURNING id" in sql


def test_the_batch_is_one_statement_with_typed_array_and_json_columns():
    inserted, session = _insert([_snapshot(1), _snapshot(2)])
    assert len(session.calls) == 1 and inserted == SnapshotInsertCounts(inserted=2)
    sql, params = session.calls[0]
    assert "data_quality_flags text[]" in sql and "projection_inputs jsonb" in sql
    rows = json.loads(params["rows"])
    assert [r["prop_id"] for r in rows] == [1, 2]
    assert rows[0]["data_quality_flags"] == ["small_sample"]
    assert rows[0]["projection_inputs"] == _snapshot().projection_inputs
    assert rows[0]["start_time"] == "2026-09-25 18:30:00+00:00"
    assert rows[0]["snapshot_at"] == "2026-09-25 13:30:00+00:00"
    assert "snapshot_at timestamptz" in sql
    assert params["eligibility_policy"] == SNAPSHOT_ELIGIBILITY_POLICY


def test_an_empty_batch_runs_no_query():
    inserted, session = _insert([])
    assert inserted == SnapshotInsertCounts() and session.calls == []


def test_insert_requires_capture_and_statement_time_before_every_observed_start():
    _, session = _insert([_snapshot()])
    sql, _ = session.calls[0]
    assert "r.snapshot_at < r.start_time" in sql
    assert "statement_timestamp() < r.start_time" in sql
    assert "GREATEST(r.snapshot_at, statement_timestamp()) < LEAST(" in sql
    for field in ("source_start_time", "match_start_time"):
        assert f"(r.projection_inputs ->> '{field}')::timestamptz" in sql
    assert "r.projection_inputs ->> 'snapshot_eligibility_policy' = :eligibility_policy" in sql
    assert "NOT IN ('live', 'completed', 'cancelled')" in sql
    assert "now()" not in sql


def test_boundary_rejections_are_not_counted_as_existing_snapshots():
    expected = SnapshotInsertCounts(inserted=2, already_stored=1, rejected_started=1)
    result, session = _insert([_snapshot(i) for i in range(4)], expected)
    assert result == expected
    sql, _ = session.calls[0]
    assert "(SELECT COUNT(*) FROM eligible) - (SELECT COUNT(*) FROM inserted) AS already_stored" in sql
    assert "(SELECT COUNT(*) FROM candidates) - (SELECT COUNT(*) FROM eligible) AS rejected_started" in sql


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
        assert params == {"version": PROJECTION_VERSION, "eligibility_policy": SNAPSHOT_ELIGIBILITY_POLICY}

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

    def test_legacy_rows_keep_the_existing_path_without_backfilled_provenance(self, graded_call):
        sql, _ = graded_call
        assert "CASE WHEN s.projection_inputs ? 'snapshot_eligibility_policy' THEN (" in sql
        assert ") ELSE TRUE END" in sql

    def test_marked_rows_cannot_be_rescued_by_a_later_start_correction(self, graded_call):
        sql, _ = graded_call
        assert "s.snapshot_at < LEAST(" in sql
        for field in ("source_start_time", "match_start_time"):
            assert f"(s.projection_inputs ->> '{field}')::timestamptz" in sql
        assert "NOT IN ('live', 'completed', 'cancelled')" in sql

    def test_an_earlier_current_match_start_can_exclude_a_marked_row(self, graded_call):
        sql, _ = graded_call
        assert "AND (m.start_utc IS NULL OR s.snapshot_at < m.start_utc)" in sql
        assert "s.projection_inputs ->> 'snapshot_eligibility_policy' = :eligibility_policy" in sql


def test_graded_mapper_turns_the_numeric_line_into_a_float():
    row = build_graded_prop_snapshot({
        "snapshot_id": 1, "player_id": 11, "match_id": 21, "tour": "WTA", "stat_type": "Total Games", "odds_type": "standard",
        "line": Decimal("21.5"), "recommendation": "UNDER", "confidence": "LEAN", "hit_probability": 0.56,
        "player_is_p1": False, "score": "6-4 6-3", "best_of": 3,
    })
    assert row.line == 21.5 and isinstance(row.line, float)
    assert (row.player_id, row.match_id) == (11, 21)


@pytest.fixture(scope="module")
def check_call() -> tuple[str, dict]:
    session = _GradedSession()
    asyncio.run(get_prop_check_snapshots(cast(AsyncSession, session), "props-v4"))
    return session.calls[0]


def _where(sql: str) -> str:
    return sql[sql.index(" WHERE "):sql.index(" ORDER BY ")]


class TestPropCheckLoader:
    def test_the_requested_version_is_the_only_one_read(self, check_call):
        sql, params = check_call
        assert "s.projection_version = :version" in sql
        assert params == {"version": "props-v4", "eligibility_policy": SNAPSHOT_ELIGIBILITY_POLICY}

    def test_it_grades_exactly_the_rows_the_26f_report_grades(self, check_call, graded_call):
        key = "s.player_id, s.match_id, s.stat_type, COALESCE(s.odds_type, ''), s.line"
        for sql, _ in (check_call, graded_call):
            assert f"SELECT DISTINCT ON ({key})" in sql
            assert f"ORDER BY {key}, s.snapshot_at DESC, s.id DESC" in sql
        assert _where(check_call[0]) == _where(graded_call[0])

    def test_the_pre_start_and_finished_match_filters_hold(self, check_call):
        sql, _ = check_call
        assert "s.snapshot_at < s.start_time" in sql
        assert "s.snapshot_at < LEAST(" in sql
        assert "m.status = 'completed' AND m.winner_id IS NOT NULL" in sql
        assert "s.player_id IN (m.p1_id, m.p2_id)" in sql

    def test_both_player_tours_are_read_for_the_wta_125_label(self, check_call):
        sql, _ = check_call
        assert "m.tour AS match_tour, p1.tour AS p1_tour, p2.tour AS p2_tour" in sql
        assert "LEFT JOIN players p1 ON p1.id = m.p1_id" in sql
        assert "LEFT JOIN players p2 ON p2.id = m.p2_id" in sql

    def test_the_probabilities_total_and_flags_are_read(self, check_call):
        sql, _ = check_call
        assert "s.start_time, s.p_over, s.p_under, s.p_push, s.market_total_games, s.data_quality_flags" in sql


def test_check_mapper_turns_the_line_into_a_float_and_flags_into_a_tuple():
    row = build_prop_check_snapshot({
        "snapshot_id": 1, "player_id": 11, "match_id": 21, "match_tour": "CHALLENGER", "p1_tour": "WTA",
        "p2_tour": None, "stat_type": "Aces", "odds_type": "goblin", "line": Decimal("3.5"), "start_time": START,
        "p_over": 0.8, "p_under": 0.2, "p_push": 0.0, "market_total_games": None,
        "data_quality_flags": ["no_market_total"], "player_is_p1": True, "score": "6-4 6-3", "best_of": 3,
    })
    assert row.line == 3.5 and isinstance(row.line, float)
    assert row.data_quality_flags == ("no_market_total",)
    assert build_prop_check_snapshot({**row.__dict__, "line": Decimal("3.5"), "data_quality_flags": None}) \
        .data_quality_flags == ()
