import asyncio
from datetime import date
from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtest.tennis_first_set_level import build_cases, fit_underdog_hold_shift, report
from app.repositories.matches import CompletedMatchScore, get_completed_match_scores
from app.repositories.players import PlayerRollingStats


class _Rows:
    def fetchall(self) -> list[tuple]:
        return [(1, "ATP", 3, 10, 20, "6-4 6-3")]


class _RecordingSession:
    def __init__(self) -> None:
        self.statement = ""
        self.params: dict[str, object] = {}

    async def execute(self, statement: object, params: dict[str, object]) -> _Rows:
        self.statement = " ".join(str(statement).split())
        self.params = params
        return _Rows()


def test_completed_scores_read_finished_atp_and_wta_matches_since_a_date() -> None:
    session = _RecordingSession()

    [match] = asyncio.run(get_completed_match_scores(cast(AsyncSession, session), date(2026, 1, 1)))

    assert "m.status = 'completed' AND m.winner_id IS NOT NULL AND m.score IS NOT NULL" in session.statement
    assert "m.tour IN ('ATP', 'WTA') AND m.match_date >= :since" in session.statement
    assert session.params == {"since": date(2026, 1, 1)}
    assert match == CompletedMatchScore(1, "ATP", 3, 10, 20, "6-4 6-3")


def _stats(hold: float) -> PlayerRollingStats:
    return cast(PlayerRollingStats, SimpleNamespace(first_in_pct=None, first_won_pct=None, second_won_pct=None, hold_pct=hold))


def test_cases_read_the_first_set_and_skip_players_without_stats() -> None:
    matches = [
        CompletedMatchScore(1, "ATP", 3, 10, 20, "6-4 3-6 7-5"),
        CompletedMatchScore(2, "WTA", 3, 10, 30, "6-2 6-1"),  # player 30 has no stats
        CompletedMatchScore(3, "ATP", 3, 10, 20, "6-4 3-5"),  # retirement, left out
    ]
    stats = {(10, None): _stats(0.8), (20, None): _stats(0.8)}

    cases, skipped = build_cases(matches, stats)

    assert skipped == 1
    [case] = cases
    assert (case.tour, case.actual_total, case.actual_p1) == ("ATP", 10, 6)
    assert case.model_p1 == pytest.approx(case.model_total / 2)


def test_favorite_is_the_higher_hold_whichever_side_it_is_on() -> None:
    matches = [
        CompletedMatchScore(1, "ATP", 3, 10, 20, "6-3 6-3"),  # p1 favored
        CompletedMatchScore(2, "ATP", 3, 20, 10, "3-6 6-3 6-3"),  # p2 favored
    ]
    cases, _ = build_cases(matches, {(10, None): _stats(0.9), (20, None): _stats(0.7)})

    assert [case.actual_favorite for case in cases] == [6, 6]
    assert cases[0].model_favorite == pytest.approx(cases[0].model_p1)
    assert cases[1].model_favorite == pytest.approx(cases[1].model_total - cases[1].model_p1)
    assert cases[0].model_favorite > cases[0].model_total / 2


def test_report_marks_a_tour_for_correction_past_the_player_games_threshold() -> None:
    lopsided = [CompletedMatchScore(i, "ATP", 3, 10, 20, "6-0 6-0") for i in range(3)]
    cases, skipped = build_cases(lopsided, {(10, None): _stats(0.9), (20, None): _stats(0.7)})

    last = report(cases, skipped).split("\n")[-1]

    assert last.startswith("  ATP") and last.endswith("correct")


def test_underdog_shift_fit_is_positive_when_underdogs_win_fewer_games() -> None:
    # The 0.7 server is the underdog; it wins none of these first sets.
    matches = [CompletedMatchScore(i, "WTA", 3, 10, 20, "6-1 6-1") for i in range(5)]
    cases, _ = build_cases(matches, {(10, None): _stats(0.9), (20, None): _stats(0.7)})

    shift = fit_underdog_hold_shift(cases, "WTA")

    assert 0.0 < shift <= 0.3
    assert fit_underdog_hold_shift(cases, "WTA") == shift


def test_report_flags_a_tour_whose_bias_exceeds_half_a_game() -> None:
    matches = [CompletedMatchScore(i, "WTA", 3, 10, 20, "6-0 6-0") for i in range(3)]
    cases, skipped = build_cases(matches, {(10, None): _stats(0.8), (20, None): _stats(0.8)})

    text = report(cases, skipped)

    assert "WTA" in text and "stop" in text.split("\n")[-1]
