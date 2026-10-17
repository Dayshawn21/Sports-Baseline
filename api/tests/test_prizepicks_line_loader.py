"""A settled line must be one PrizePicks offered before the match, on the match it
was really for."""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.repositories.props import (
    build_prizepicks_line_row,
    get_prizepicks_link_coverage,
    get_settleable_prizepicks_lines,
)


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
    asyncio.run(get_settleable_prizepicks_lines(cast(AsyncSession, session)))
    return session.statement


class TestNoLookahead:
    def test_the_snapshot_is_strictly_before_the_start(self, sql):
        assert "p.fetched_at < m.start_utc" in sql

    def test_only_the_latest_pre_start_snapshot_per_key_is_kept(self, sql):
        assert (
            "MAX(p.fetched_at) OVER ( PARTITION BY p.player_id, p.match_id, p.stat_type, "
            "COALESCE(p.odds_type, '') )"
        ) in sql
        assert "WHERE fetched_at = closing_at" in sql

    def test_the_closing_window_is_taken_after_the_pre_start_filter(self, sql):
        # A window over unfiltered rows would pick a post-start snapshot as the close.
        eligible = sql.split("WITH eligible AS (")[1].split(") SELECT DISTINCT ON")[0]
        assert "MAX(p.fetched_at) OVER" in eligible
        assert "p.fetched_at < m.start_utc" in eligible


class TestRightMatch:
    def test_the_player_is_on_one_side_of_the_match(self, sql):
        assert "p.player_id IN (m.p1_id, m.p2_id)" in sql

    def test_a_link_to_a_match_far_from_the_prop_start_is_refused(self, sql):
        assert "ABS(EXTRACT(EPOCH FROM (m.start_utc - p.start_time))) <= 12 * 3600" in sql

    def test_only_settled_prizepicks_matches(self, sql):
        assert "p.source = 'prizepicks'" in sql
        assert "m.status = 'completed' AND m.winner_id IS NOT NULL" in sql


class TestFlags:
    def test_live_and_promo_rows_are_flagged_not_filtered(self, sql):
        assert "AS is_live" in sql and "AS is_promo" in sql
        assert "flash_sale_line_score" in sql


class _CoverageResult(_Result):
    def one(self) -> dict:
        return {
            "rows": 0, "rows_linked": 0, "player_matches": 0, "player_matches_settled": 0,
            "box_score_exact_date": 0, "box_score_unique_in_window": 0,
        }


class _CoverageSession(_RecordingSession):
    async def execute(self, statement: TextClause, params: dict | None = None) -> _CoverageResult:
        self.statement = " ".join(str(statement).split())
        return _CoverageResult()


@pytest.fixture(scope="module")
def coverage_sql() -> str:
    session = _CoverageSession()
    asyncio.run(get_prizepicks_link_coverage(cast(AsyncSession, session)))
    return session.statement


class TestCoverage:
    def test_box_scores_join_on_player_and_result(self, coverage_sql):
        assert coverage_sql.count("s.player_id = l.player_id AND s.result = l.result") == 2

    def test_exact_date_and_window_joins(self, coverage_sql):
        assert "AND s.match_date = l.match_date" in coverage_sql
        assert "s.match_date BETWEEN l.match_date - 14 AND l.match_date + 3" in coverage_sql
        assert "window_candidates = 1" in coverage_sql

    def test_box_scores_are_only_sought_for_settled_matches(self, coverage_sql):
        assert "m.status = 'completed' AND m.winner_id IS NOT NULL" in coverage_sql
        assert "WHERE l.settled" in coverage_sql


def test_mapper_turns_the_numeric_line_into_a_float():
    start = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)
    row = build_prizepicks_line_row({
        "prop_id": 1, "player_id": 2, "match_id": 3, "tour": "ATP",
        "stat_type": "Total Games", "odds_type": "standard", "line": Decimal("22.5"),
        "fetched_at": start.replace(hour=9), "start_utc": start, "player_is_p1": False,
        "score": "6-4 6-3", "best_of": 3, "is_live": False, "is_promo": False,
    })
    assert row.line == 22.5 and isinstance(row.line, float)
    assert row.player_is_p1 is False
