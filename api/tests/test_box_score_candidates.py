"""The candidate loader must hand the join the right opponent and the widest fair window."""
import asyncio
from datetime import date
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.repositories.player_match_stats import get_box_score_candidates, group_candidate_rows


class _Result:
    def mappings(self):
        return self

    def all(self) -> list:
        return []


class _RecordingSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, statement: TextClause, params: dict | None = None) -> _Result:
        self.calls.append((" ".join(str(statement).split()), params or {}))
        return _Result()


@pytest.fixture(scope="module")
def call() -> tuple[str, dict]:
    session = _RecordingSession()
    asyncio.run(get_box_score_candidates(cast(AsyncSession, session), [(11, 21), (12, 22)]))
    return session.calls[0]


def test_the_opponent_is_the_other_side_of_the_match(call):
    sql, _ = call
    assert "JOIN players opp ON opp.id = CASE WHEN m.p1_id = pr.player_id THEN m.p2_id ELSE m.p1_id END" in sql


def test_candidates_are_the_players_own_rows_in_the_window(call):
    sql, params = call
    assert "s.player_id = pr.player_id" in sql
    assert "BETWEEN m.match_date - CAST(:days_before AS int) AND m.match_date + CAST(:days_after AS int)" in sql
    assert (params["days_before"], params["days_after"]) == (14, 3)


def test_pairs_are_passed_as_parallel_arrays(call):
    _, params = call
    assert params["player_ids"] == [11, 12] and params["match_ids"] == [21, 22]


def test_break_chances_are_loaded_for_the_evidence_panel(call):
    sql, _ = call
    assert "s.break_chances_created" in sql


def test_only_settled_matches(call):
    sql, _ = call
    assert "m.winner_id IS NOT NULL" in sql


def test_no_pairs_runs_no_query():
    session = _RecordingSession()
    assert asyncio.run(get_box_score_candidates(cast(AsyncSession, session), [])) == {}
    assert session.calls == []


def _row(stats_id, **kw) -> dict:
    row = dict(
        player_id=11, match_id=21, match_date=date(2026, 7, 12), match_score="7-6 6-7 3-6 4-6",
        p1_won=False, result="W", opponent_name="Alexander Zverev",
        stats_id=stats_id, stats_date=date(2026, 6, 29), stats_result="W",
        stats_opponent_name="Alexander Zverev", stats_score="6-7(7) 7-6(2) 6-3 6-4",
        aces=12, double_faults=2, break_points_converted=3, break_chances_created=7,
        source="tennisabstract",
    )
    row.update(kw)
    return row


def test_rows_group_per_pair_with_a_winner_first_match_score():
    grouped = group_candidate_rows([_row(1), _row(2, stats_opponent_name="Novak Djokovic")])
    context = grouped[(11, 21)]
    assert context.match_score_winner_first == "6-7 7-6 6-3 6-4"
    assert [c.stats_id for c in context.candidates] == [1, 2]
    assert context.candidates[0].break_chances_created == 7


@pytest.mark.parametrize("source", ["tennisabstract", "tennismylife"])
def test_candidate_keeps_its_source(source):
    grouped = group_candidate_rows([_row(1, source=source)])
    assert grouped[(11, 21)].candidates[0].source == source


def test_a_pair_with_no_box_score_keeps_an_empty_candidate_list():
    empty = {k: None for k in ("stats_date", "stats_result", "stats_opponent_name",
                               "stats_score", "aces", "double_faults", "break_points_converted",
                               "break_chances_created")}
    grouped = group_candidate_rows([_row(None, **empty)])
    assert grouped[(11, 21)].candidates == []
