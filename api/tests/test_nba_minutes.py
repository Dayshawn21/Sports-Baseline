from dataclasses import replace
from datetime import date, timedelta

import pytest

from app.core.nba_line_only import LINE_ONLY_COLUMNS
from app.core.nba_minutes import (
    MAX_MINUTE_SHIFT, MAX_MINUTES, NBA_MINUTES_FIRST_HISTORY_SEASON, NBA_MINUTES_MODEL_VERSION, ROTATION_MINUTES,
    FIT_K_RANGE, MIN_FIT_CASES, Availability, FitCase, NbaRosterRow, RosterIndex, TeammateAvailability, availability, fit_rotation_coefficient,
    k_in_range, minutes_change,
    project_minutes_line,
)
from app.core.nba_projection import project_line
from app.core.nba_projection_backtest import NbaHistoryRow
from app.nba.markets import NbaPropMarket

TEAM = 1
OTHER_TEAM = 2
STAR, MATE, BENCH = 10, 20, 30
START = date(2024, 11, 1)


def _row(player: int, game: int, *, team: int = TEAM, minutes: float | None = 30.0, dnp: bool = False) -> NbaRosterRow:
    return NbaRosterRow(
        player_id=player, game_id=game, team_id=team, season=2024, game_date=START + timedelta(days=game),
        did_not_play=dnp, minutes=None if dnp else minutes,
    )


def _index(games: list[list[NbaRosterRow]]) -> RosterIndex:
    index = RosterIndex()
    for rows in games:
        index.advance(rows)
    return index


def _game(game: int, *, mate_plays: bool = True, mate_minutes: float = 30.0) -> list[NbaRosterRow]:
    rows = [_row(STAR, game)]
    if mate_plays:
        rows.append(_row(MATE, game, minutes=mate_minutes))
    return rows


def test_constants() -> None:
    assert NBA_MINUTES_FIRST_HISTORY_SEASON == 2023
    assert ROTATION_MINUTES == 15.0
    assert NBA_MINUTES_MODEL_VERSION == "nba-minutes-v1"
    assert (MAX_MINUTE_SHIFT, MAX_MINUTES) == (10.0, 42.0)
    assert MIN_FIT_CASES == 2000 and FIT_K_RANGE == (0.0, 2.0)


def test_full_availability_matching_the_window_has_no_delta() -> None:
    index = _index([_game(g) for g in range(1, 21)])

    result = availability(index, STAR, TEAM, index.previous_game_players(TEAM))

    assert [(m.player_id, m.minutes, m.window_share, m.available) for m in result.teammates] == [(MATE, 30.0, 1.0, True)]
    assert result.team_delta == 0.0
    assert result.out_player_ids == ()


def test_a_game_on_the_projected_date_is_never_an_input() -> None:
    index = _index([_game(g) for g in range(1, 21)])
    # The game being projected: its rows are not advanced until after the projection.
    tonight = [_row(STAR, 21), _row(MATE, 21, minutes=2.0)]

    before = availability(index, STAR, TEAM, index.previous_game_players(TEAM))
    index.advance(tonight)
    after = availability(index, STAR, TEAM, index.previous_game_players(TEAM))

    assert before.teammates[0].minutes == 30.0
    assert after.teammates[0].minutes == pytest.approx(27.2)


def test_teammate_below_rotation_minutes_is_excluded() -> None:
    games = [_game(g) + [_row(BENCH, g, minutes=14.9)] for g in range(1, 21)]
    index = _index(games)

    result = availability(index, STAR, TEAM, frozenset())

    assert [m.player_id for m in result.teammates] == [MATE]


def test_teammate_traded_away_is_excluded() -> None:
    games = [_game(g) for g in range(1, 21)]
    games.append([_row(STAR, 21), _row(MATE, 21, team=OTHER_TEAM)])
    index = _index(games)

    assert availability(index, STAR, TEAM, frozenset()).teammates == ()


def test_window_share_counts_the_games_the_teammate_played_with_the_player() -> None:
    index = _index([_game(g, mate_plays=g > 5) for g in range(1, 21)])

    mate = availability(index, STAR, TEAM, frozenset({MATE})).teammates[0]

    assert mate.window_share == 0.75
    # Back in tonight after missing a quarter of the window: minutes come back from the player.
    assert availability(index, STAR, TEAM, frozenset({MATE})).team_delta == pytest.approx(30.0 * 0.25)


def test_a_did_not_play_row_and_a_missing_row_both_read_as_not_played() -> None:
    games = [_game(g) for g in range(1, 19)]
    games.append([_row(STAR, 19), _row(MATE, 19, dnp=True)])
    games.append([_row(STAR, 20)])
    index = _index(games)

    assert availability(index, STAR, TEAM, frozenset()).teammates[0].window_share == 0.9
    assert MATE not in index.previous_game_players(TEAM)


def test_previous_game_sees_a_first_absence_one_game_late_and_the_oracle_at_once() -> None:
    index = _index([_game(g) for g in range(1, 21)])
    tonight_played = frozenset({STAR})

    previous = availability(index, STAR, TEAM, index.previous_game_players(TEAM))
    oracle = availability(index, STAR, TEAM, tonight_played)
    assert previous.team_delta == 0.0
    assert oracle.team_delta == -30.0 and oracle.out_player_ids == (MATE,)

    index.advance([_row(STAR, 21)])
    next_game = availability(index, STAR, TEAM, index.previous_game_players(TEAM))
    assert next_game.out_player_ids == (MATE,)
    assert next_game.team_delta == pytest.approx(-30.0 * 0.95)


def test_a_window_with_games_for_another_team_is_team_changed() -> None:
    games = [[_row(STAR, 1, team=OTHER_TEAM)]] + [_game(g) for g in range(2, 21)]
    index = _index(games)

    result = availability(index, STAR, TEAM, index.previous_game_players(TEAM))

    assert result.team_changed and result.teammates == () and result.team_delta == 0.0


def test_null_minutes_are_skipped_in_a_teammates_mean_but_still_count_as_played() -> None:
    games = [_game(g) for g in range(1, 20)]
    games.append([_row(STAR, 20), _row(MATE, 20, minutes=None)])
    index = _index(games)

    mate = availability(index, STAR, TEAM, frozenset({MATE})).teammates[0]

    assert mate.minutes == 30.0 and mate.window_share == 1.0


def _history(games: int, *, minutes: float | None = 30.0, points: int | None = 20, rebounds: int = 6) -> list[NbaHistoryRow]:
    stats: dict[str, int | bool | None] = {column: 0 for column in LINE_ONLY_COLUMNS}
    stats.update(did_not_play=False, points=points, rebounds=rebounds)
    return [
        NbaHistoryRow(
            player_id=STAR, game_id=g, season=2024, game_date=START + timedelta(days=g), game_type="REG",
            did_not_play=False, minutes=minutes, stats=stats,
        )
        for g in range(1, games + 1)
    ]


def _available(*mates: tuple[float, float, bool], team_changed: bool = False) -> Availability:
    return Availability(
        teammates=tuple(TeammateAvailability(100 + i, m, share, up) for i, (m, share, up) in enumerate(mates)),
        team_changed=team_changed,
    )


def test_no_change_serves_exactly_the_reference_projection() -> None:
    prior = _history(20)
    for market in NbaPropMarket:
        result = project_minutes_line(prior, _available((30.0, 1.0, True)), market, k=0.5)
        assert result.minutes_change == 0.0
        assert result.projection == project_line(prior, market, 10.5).projection
        assert result.model_version == "nba-minutes-v1" and result.flags == ()


def test_a_vacated_teammate_moves_minutes_by_the_players_share() -> None:
    prior = _history(20)

    alone = project_minutes_line(prior, _available((30.0, 1.0, False)), NbaPropMarket.POINTS, k=0.2)
    shared = project_minutes_line(
        prior, _available((30.0, 1.0, False), (30.0, 1.0, True)), NbaPropMarket.POINTS, k=0.2,
    )

    # Worked by hand: 20 points in 30 minutes; D = -30; change = 0.2 * 30 * 30 / M.
    assert alone.minutes_change == pytest.approx(6.0) and alone.projection == pytest.approx(24.0)
    assert shared.minutes_change == pytest.approx(3.0) and shared.projection == pytest.approx(22.0)
    assert alone.reference == 20.0 and alone.rate == pytest.approx(2 / 3)
    assert alone.out_player_ids == (100,)


def test_both_clamps_bind() -> None:
    assert minutes_change(30.0, -30.0, 0.0, k=1.0) == MAX_MINUTE_SHIFT
    assert minutes_change(30.0, 60.0, 0.0, k=1.0) == -MAX_MINUTE_SHIFT
    assert minutes_change(38.0, -38.0, 0.0, k=1.0) == pytest.approx(MAX_MINUTES - 38.0)


def test_a_combos_rate_is_the_sum_of_its_components_rates() -> None:
    prior = _history(20)
    vacated = _available((30.0, 1.0, False))

    combo = project_minutes_line(prior, vacated, NbaPropMarket.POINTS_REBOUNDS, k=0.2)
    parts = [project_minutes_line(prior, vacated, m, k=0.2) for m in (NbaPropMarket.POINTS, NbaPropMarket.REBOUNDS)]

    assert combo.rate == pytest.approx(sum(p.rate or 0.0 for p in parts))
    assert combo.projection == pytest.approx(sum(p.projection or 0.0 for p in parts))


def test_no_rate_and_team_changed_fall_back_to_the_reference() -> None:
    no_minutes = _history(20, minutes=None)
    # The one row with minutes has no points, so no row carries both.
    no_minutes[-1] = replace(no_minutes[-1], minutes=25.0, stats={**no_minutes[-1].stats, "points": None})
    no_rate = project_minutes_line(no_minutes, _available((30.0, 1.0, False)), NbaPropMarket.POINTS, k=0.2)
    changed = project_minutes_line(
        _history(20), _available(team_changed=True), NbaPropMarket.POINTS, k=0.2,
    )

    assert no_rate.flags == ("no_rate",) and no_rate.minutes_change == 0.0 and no_rate.projection == 20.0
    assert changed.flags == ("team_changed",) and changed.projection == 20.0


@pytest.mark.parametrize(("games", "minutes"), [(10, 20.0), (9, 20.0), (10, 19.9), (12, 25.0)])
def test_eligibility_matches_the_reference_at_its_bounds(games: int, minutes: float) -> None:
    prior = _history(games, minutes=minutes)

    ours = project_minutes_line(prior, _available(), NbaPropMarket.POINTS, k=0.2)
    reference = project_line(prior, NbaPropMarket.POINTS, 15.5)

    assert ours.projection == reference.projection
    assert (ours.projection is None) == (games < 10 or minutes < 20.0)
    if reference.flags and reference.flags[0] in ("few_prior_games", "low_minutes"):
        assert ours.flags == (reference.flags[0],)


def _fit_cases(k: float, count: int) -> list[FitCase]:
    cases = []
    for i in range(count):
        delta = -float(i % 7 + 1) * 5.0 if i % 2 else float(i % 5 + 1) * 4.0
        case = FitCase(actual_minutes=0.0, player_minutes=30.0, team_delta=delta, available_minutes=90.0)
        # Symmetric noise that cancels in pairs, so the fit recovers k exactly.
        noise = 0.5 if i % 4 < 2 else -0.5
        cases.append(replace(case, actual_minutes=30.0 + k * case.x + noise * (case.x != 0.0)))
    return cases


def test_the_fit_recovers_a_known_coefficient() -> None:
    cases = _fit_cases(0.8, 2400) + [FitCase(31.0, 30.0, 0.0, 90.0)] * 50

    assert fit_rotation_coefficient(cases) == pytest.approx(0.8, abs=0.01)


def test_the_fit_refuses_below_the_minimum_informative_cases() -> None:
    uninformative = [FitCase(30.0, 30.0, 0.0, 90.0)] * 5000

    with pytest.raises(ValueError, match="2000"):
        fit_rotation_coefficient(_fit_cases(0.8, MIN_FIT_CASES - 1) + uninformative)
    assert fit_rotation_coefficient(_fit_cases(0.8, MIN_FIT_CASES)) == pytest.approx(0.8, abs=0.02)


def test_a_coefficient_outside_the_range_stops_the_feature() -> None:
    assert k_in_range(0.0) and k_in_range(2.0) and k_in_range(0.7)
    assert not k_in_range(-0.01) and not k_in_range(2.01)
