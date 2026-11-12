import dataclasses
import datetime as dt

import pytest

from app.core.nhl_projection_backtest import (
    ARMS, LAST_10_ARM, REFERENCE_ARM, NhlHistoryRow, NhlReplayCase, eligible_case, prior_toi_minutes, replay_cases,
)

START = dt.date(2024, 10, 1)
TOI_15 = 15 * 60


def skater(day: int, *, player_id: int = 1, season: int = 2024, position: str | None = "C", shots: int | None = 3,
           toi: int | None = TOI_15, **stats: int | None) -> NhlHistoryRow:
    return NhlHistoryRow(
        player_id=player_id, game_id=player_id * 1000 + day, season=season, game_date=START + dt.timedelta(days=day),
        game_type="REG", position=position, is_goalie=False, started=True,
        stats={"shots": shots, "time_on_ice_seconds": toi, "points": 1, "faceoffs_won": 8, **stats},
    )


def goalie(day: int, *, player_id: int = 30, started: bool = True, saves: int | None = 25) -> NhlHistoryRow:
    return NhlHistoryRow(
        player_id=player_id, game_id=player_id * 1000 + day, season=2024, game_date=START + dt.timedelta(days=day),
        game_type="REG", position="G", is_goalie=True, started=started,
        stats={"saves": saves, "goals_against": 2, "time_on_ice_seconds": 3600},
    )


def run(rows: list[NhlHistoryRow], arm: str = REFERENCE_ARM, season: int = 2024) -> list[NhlReplayCase]:
    return replay_cases(sorted(rows, key=lambda row: row.game_date), season, ARMS[arm])


def market(cases: list[NhlReplayCase], name: str, game_id: int | None = None) -> list[NhlReplayCase]:
    return [case for case in cases if case.market == name and (game_id is None or case.game_id == game_id)]


def test_a_same_date_game_is_not_an_input() -> None:
    rows = [skater(day, shots=day) for day in range(10)] + [skater(10, shots=10), skater(10, player_id=1, shots=99)]
    cases = market(run(rows), "shots_on_goal")
    assert {case.game_id: case.projection for case in cases} == {1010: 4.5}


def test_windows_cross_from_the_prior_season_but_only_the_target_season_is_scored() -> None:
    prior_season = [skater(day, season=2023, shots=2) for day in range(10)]
    target = skater(20, shots=5)
    cases = market(run(prior_season + [target]), "shots_on_goal")
    assert [(case.game_id, case.projection, case.actual) for case in cases] == [(1020, 2.0, 5.0)]


def test_eligibility_at_exactly_ten_games_and_twelve_minutes() -> None:
    history = [skater(day, toi=12 * 60) for day in range(10)]
    assert eligible_case(skater(10), history)
    assert not eligible_case(skater(10), history[1:])
    assert not eligible_case(skater(10), [skater(day, toi=12 * 60 - 1) for day in range(10)])


def test_null_toi_is_ignored_in_the_eligibility_mean() -> None:
    history = [skater(day, toi=None if day < 5 else 13 * 60) for day in range(10)]
    assert prior_toi_minutes(history) == 13.0
    assert eligible_case(skater(10), history)
    assert prior_toi_minutes([skater(day, toi=None) for day in range(10)]) is None
    assert not eligible_case(skater(10), [skater(day, toi=None) for day in range(10)])


def test_a_null_stat_is_skipped_as_an_input_and_as_an_actual() -> None:
    rows = [skater(day, shots=None if day == 3 else 4) for day in range(10)] + [skater(10, shots=None), skater(11, shots=6)]
    cases = market(run(rows), "shots_on_goal")
    assert [(case.game_id, case.projection) for case in cases] == [(1011, 4.0)]


def test_time_on_ice_is_scored_in_minutes() -> None:
    rows = [skater(day, toi=18 * 60) for day in range(10)] + [skater(10, toi=20 * 60)]
    [case] = market(run(rows), "time_on_ice")
    assert (case.projection, case.actual) == (18.0, 20.0)
    assert case.prior_toi_minutes == 18.0


def test_faceoffs_are_scored_for_centers_only() -> None:
    history = [skater(day) for day in range(10)]
    wing = [skater(day, player_id=2, position="LW") for day in range(11)]
    center = history + [skater(10)]
    cases = run(center + wing)
    assert {case.player_id for case in market(cases, "faceoffs_won")} == {1}
    assert {case.player_id for case in market(cases, "shots_on_goal")} == {1, 2}


def test_skaters_are_not_scored_on_goalie_markets_and_goalies_not_on_skater_markets() -> None:
    cases = run([skater(day) for day in range(11)] + [goalie(day) for day in range(6)])
    assert {case.market for case in cases if case.player_id == 1}.isdisjoint({"goalie_saves", "goals_allowed"})
    assert {case.market for case in cases if case.player_id == 30} == {"goalie_saves", "goals_allowed"}


def test_a_goalie_case_needs_a_start_and_five_prior_starts() -> None:
    starts = [goalie(day) for day in range(5)]
    assert eligible_case(goalie(5), starts)
    assert not eligible_case(goalie(5), starts[1:])
    assert not eligible_case(goalie(5, started=False), starts)


def test_a_goalie_relief_appearance_is_neither_a_case_nor_an_input() -> None:
    rows = [goalie(day, saves=20) for day in range(5)] + [goalie(5, started=False, saves=40), goalie(6, saves=30)]
    cases = market(run(rows), "goalie_saves")
    assert [(case.game_id, case.projection, case.actual) for case in cases] == [(30006, 20.0, 30.0)]


def test_reference_uses_twenty_games_and_last_10_uses_ten() -> None:
    rows = [skater(day, shots=0) for day in range(10)] + [skater(day, shots=10) for day in range(10, 20)] + [skater(20, shots=5)]
    [reference] = market(run(rows, REFERENCE_ARM), "shots_on_goal", 1020)
    [last_10] = market(run(rows, LAST_10_ARM), "shots_on_goal", 1020)
    assert reference.projection == 5.0
    assert last_10.projection == 10.0


def test_reference_uses_every_game_when_ten_to_nineteen_exist() -> None:
    rows = [skater(day, shots=day) for day in range(12)] + [skater(12, shots=1)]
    [case] = market(run(rows), "shots_on_goal", 1012)
    assert case.projection == pytest.approx(5.5)


def test_both_arms_score_the_same_cases() -> None:
    rows = [skater(day) for day in range(15)]
    assert [case.key for case in run(rows, REFERENCE_ARM)] == [case.key for case in run(rows, LAST_10_ARM)]


@pytest.mark.parametrize("arm", [REFERENCE_ARM, LAST_10_ARM])
def test_matchup_fields_leave_existing_arms_unchanged(arm: str) -> None:
    rows = [skater(day, shots=day % 5) for day in range(25)] + [goalie(day, saves=20 + day) for day in range(12)]
    with_matchup = [dataclasses.replace(row, team_id=1, opponent_team_id=2) for row in rows]
    assert run(with_matchup, arm) == run(rows, arm)
