import datetime as dt
from collections.abc import Sequence

import pytest

from app.core.nhl_goalie_adjustment import ADJUSTED_MARKETS, GoalieRecord, Matchup, goalie_multiplier, goalie_record
from app.core.nhl_projection_backtest import (
    ARMS, OPP_GOALIE_BETA_BY_MARKET, REFERENCE_ARM, MatchupArm, NhlHistoryRow, NhlReplayCase, opp_goalie_arm,
    opp_goalie_holdout_candidates, replay_cases, replay_matchup_cases,
)
from app.nhl.markets import NhlLineOnlyMarket

START = dt.date(2024, 10, 1)
SKATER, OWN_GOALIE, OPP_STARTER, OPP_RELIEF = 1, 40, 30, 31
TEAM, OPPONENT = 1, 2
CASE_DAY = 10


def game_id(day: int) -> int:
    return 100 + day


def skater(day: int, *, opponent: int | None = OPPONENT, points: int = 1) -> NhlHistoryRow:
    return NhlHistoryRow(
        player_id=SKATER, game_id=game_id(day), season=2024, game_date=START + dt.timedelta(days=day),
        game_type="REG", position="C", is_goalie=False, started=True,
        stats={"shots": 3, "points": points, "goals": 0, "assists": 1, "power_play_points": 0,
               "time_on_ice_seconds": 900},
        team_id=TEAM, opponent_team_id=opponent,
    )


def goalie(day: int, player_id: int, team: int, *, saves: int = 27, shots: int | None = 30,
           started: bool = True, game: int | None = None) -> NhlHistoryRow:
    return NhlHistoryRow(
        player_id=player_id, game_id=game_id(day) if game is None else game, season=2024,
        game_date=START + dt.timedelta(days=day), game_type="REG", position="G", is_goalie=True, started=started,
        stats={"saves": saves, "shots_against": shots, "goals_against": None if shots is None else shots - saves,
               "time_on_ice_seconds": 3600},
        team_id=team, opponent_team_id=TEAM if team == OPPONENT else OPPONENT,
    )


def history(extra: Sequence[NhlHistoryRow] = ()) -> list[NhlHistoryRow]:
    rows = [skater(day) for day in range(CASE_DAY + 1)]
    rows += [goalie(day, OPP_STARTER, OPPONENT) for day in range(CASE_DAY + 1)]
    rows += [goalie(day, OWN_GOALIE, TEAM, saves=29) for day in range(CASE_DAY + 1)]
    return sorted([*rows, *extra], key=lambda row: (row.game_date, row.game_id, row.is_goalie, row.player_id))


def capture(seen: list[Matchup]) -> MatchupArm:
    def arm(prior: Sequence[NhlHistoryRow], market: NhlLineOnlyMarket, matchup: Matchup) -> float | None:
        if market is NhlLineOnlyMarket.POINTS:
            seen.append(matchup)
        return 1.0
    return arm


def case_matchup(rows: list[NhlHistoryRow]) -> Matchup:
    seen: list[Matchup] = []
    replay_matchup_cases(rows, 2024, capture(seen))
    # Only the case day is eligible: the skater has ten prior games from day 10 on.
    return seen[-1]


def test_the_opponents_starter_is_used_not_the_own_goalie_or_a_relief_goalie() -> None:
    relief = goalie(CASE_DAY, OPP_RELIEF, OPPONENT, saves=0, shots=10, started=False)
    matchup = case_matchup(history([relief]))
    # Ten prior opposing starts at 27 of 30, none of the own goalie's 29s or the relief appearance.
    assert matchup.opposing_goalie == GoalieRecord(27 * 10, 30 * 10)


def test_same_day_starts_are_not_inputs_to_the_record_or_the_league() -> None:
    other_game = goalie(CASE_DAY, 50, 9, saves=0, shots=40, game=999)
    matchup = case_matchup(history([other_game]))
    assert matchup.opposing_goalie == GoalieRecord(27 * 10, 30 * 10)
    # Prior days only: both teams' goalies, ten starts each.
    assert matchup.league_save_pct == pytest.approx((27 + 29) / 60)


def test_only_the_last_twenty_starts_count() -> None:
    old_starts = [goalie(day, OPP_STARTER, OPPONENT, saves=0, game=500 + day) for day in range(-11, 0)]
    matchup = case_matchup(history(old_starts))
    # 21 prior starts: the oldest zero-save start drops, ten remain alongside the ten 27s.
    assert matchup.opposing_goalie == GoalieRecord(27 * 10, 30 * 20)


def test_starts_missing_shots_against_are_skipped() -> None:
    record = goalie_record([{"saves": 20, "shots_against": None}, {"saves": 25, "shots_against": 28}])
    assert record == GoalieRecord(25, 28)


def test_a_missing_opposing_starter_is_neutral_and_counted() -> None:
    rows = [row for row in history() if not (row.player_id == SKATER and row.game_id == game_id(CASE_DAY))]
    rows = sorted(
        [*rows, skater(CASE_DAY, opponent=None)], key=lambda row: (row.game_date, row.is_goalie, row.player_id),
    )
    seen: list[Matchup] = []
    cases = replay_matchup_cases(rows, 2024, capture(seen))
    assert seen[-1].opposing_goalie is None and seen[-1].multiplier() == 1.0
    skater_cases = [case for case in cases if case.player_id == SKATER]
    assert skater_cases and {case.opposing_starter_found for case in skater_cases} == {False}


def test_a_known_starter_with_no_prior_starts_reads_the_league() -> None:
    rows = [row for row in history() if row.player_id != OPP_STARTER]
    rows.append(goalie(CASE_DAY, 77, OPPONENT))
    matchup = case_matchup(sorted(rows, key=lambda row: (row.game_date, row.is_goalie, row.player_id)))
    assert matchup.opposing_goalie == GoalieRecord(0, 0)
    assert matchup.multiplier() == pytest.approx(1.0)


def test_the_arm_scores_the_same_cases_as_reference_and_scales_only_adjusted_markets() -> None:
    rows = history()
    reference = replay_cases(rows, 2024, ARMS[REFERENCE_ARM])
    arm = opp_goalie_arm({NhlLineOnlyMarket.POINTS: 1.0, NhlLineOnlyMarket.SHOTS_ON_GOAL: 0.5})
    adjusted = replay_matchup_cases(rows, 2024, arm)
    assert [case.key for case in adjusted] == [case.key for case in reference]
    multiplier = goalie_multiplier(GoalieRecord(27 * 10, 30 * 10), (27 + 29) / 60)
    by_key: dict[tuple[int, int, str], NhlReplayCase] = {case.key: case for case in reference}
    for case in adjusted:
        base = by_key[case.key].projection
        expected = {"points": base * multiplier, "shots_on_goal": base * multiplier ** 0.5}.get(case.market, base)
        assert case.projection == pytest.approx(expected)
        assert case.opposing_starter_found is (True if case.player_id == SKATER else None)


def test_an_empty_exponent_map_reproduces_reference() -> None:
    rows = history()
    reference = replay_cases(rows, 2024, ARMS[REFERENCE_ARM])
    adjusted = replay_matchup_cases(rows, 2024, opp_goalie_arm({}))
    assert [(case.key, case.projection) for case in adjusted] == [(case.key, case.projection) for case in reference]


def test_the_committed_development_pick_leaves_no_holdout_candidate() -> None:
    assert OPP_GOALIE_BETA_BY_MARKET == {market: 0.0 for market in ADJUSTED_MARKETS}
    assert opp_goalie_holdout_candidates() == []
