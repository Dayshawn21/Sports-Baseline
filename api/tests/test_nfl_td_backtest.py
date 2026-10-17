from math import log

import pytest

from app.core.nfl_projection import anytime_td_probability
from app.core.nfl_red_zone import NflRedZoneCoefficients
from app.core.nfl_snap_share import NflSnapCoefficients
from app.core.nfl_end_zone import NflEndZoneCoefficients
from app.core.nfl_td_backtest import (
    NflSnapRow,
    NflTdBacktestCase,
    NflWeeklyTdRow,
    baseline_probability,
    brier,
    build_cases,
    case_snap_share,
    log_loss,
    red_zone_probability,
    score,
    score_by_position,
    snap_share_probability,
    implied_total_probability,
    production_probability,
    end_zone_probability,
)

RB, OTHER_RB = 1, 2


def _row(player: int, season: int, week: int, touchdowns: int = 0, position: str | None = "RB",
         rz: tuple[int, int, int, int] | None = (1, 0, 0, 0), end_zone_targets: int | None = 0, total: float | None = 47.0,
         spread: float | None = 3.0, home_moneyline: int | None = -150,
         away_moneyline: int | None = 130, is_home: bool = True) -> NflWeeklyTdRow:
    counts = rz if rz is not None else (None, None, None, None)
    return NflWeeklyTdRow(
        player, position, season, week, touchdowns, *counts, end_zone_targets,
        total, spread, home_moneyline, away_moneyline, is_home,
    )


def _history(player: int, weeks: range, season: int = 2024, touchdowns: int = 0) -> list[NflWeeklyTdRow]:
    return [_row(player, season, week, touchdowns) for week in weeks]


def _case_for(cases: list[NflTdBacktestCase], player: int, season: int, week: int) -> NflTdBacktestCase:
    return next(case for case in cases if (case.player_id, case.season, case.week) == (player, season, week))


def test_a_case_never_sees_its_own_week_or_later_weeks() -> None:
    rows = _history(RB, range(1, 5)) + [
        _row(RB, 2024, 5, touchdowns=3, rz=(9, 9, 9, 9)),
        _row(RB, 2024, 6, touchdowns=3, rz=(9, 9, 9, 9)),
    ]

    case = _case_for(build_cases(rows, frozenset({2024})), RB, 2024, 5)

    assert case.scored is True
    assert [(entry.season, entry.games, entry.touchdowns_per_game) for entry in case.td_seasons] == [(2024, 4, 0.0)]
    assert case.red_zone_seasons[0].rates.rz20_carries == 1.0
    assert case.red_zone_seasons[0].rates.rz5_carries == 0.0


def test_position_rates_exclude_same_week_and_later_games() -> None:
    # A teammate's week-5 and week-6 explosions must not leak into the week-5 position rate.
    rows = _history(RB, range(1, 5)) + _history(OTHER_RB, range(1, 5), touchdowns=1) + [
        _row(RB, 2024, 5),
        _row(OTHER_RB, 2024, 5, touchdowns=4, rz=(9, 9, 9, 9)),
        _row(OTHER_RB, 2024, 6, touchdowns=4, rz=(9, 9, 9, 9)),
    ]

    case = _case_for(build_cases(rows, frozenset({2024})), RB, 2024, 5)

    # Eight pre-week RB games, four with a TD each.
    assert case.position_td_rate == pytest.approx(0.5)
    assert case.position_red_zone.rz20_carries == pytest.approx(1.0)
    assert case.position_red_zone.rz5_carries == pytest.approx(0.0)


def test_thin_history_non_skill_positions_and_unselected_seasons_are_not_evaluated() -> None:
    rows = (
        _history(RB, range(1, 4)) + [_row(RB, 2024, 4)]
        + [_row(9, 2024, week, position="K") for week in range(1, 7)]
        + _history(OTHER_RB, range(1, 18), season=2023) + [_row(OTHER_RB, 2024, 1)]
    )

    cases = build_cases(rows, frozenset({2024}))

    # RB has only 3 pre-week games at week 4; the kicker never counts; OTHER_RB's
    # 2023 games are history for its 2024 week-1 case, not cases themselves.
    assert [(case.player_id, case.season, case.week) for case in cases] == [(OTHER_RB, 2024, 1)]


def test_unloaded_play_by_play_games_are_not_red_zone_evidence() -> None:
    rows = [_row(RB, 2024, week, rz=None) for week in range(1, 5)] + [_row(RB, 2024, 5)]

    case = _case_for(build_cases(rows, frozenset({2024})), RB, 2024, 5)

    assert case.td_seasons[0].games == 4
    assert case.red_zone_seasons[0].games == 0


def test_baseline_probability_is_the_production_baseline_unrounded() -> None:
    rows = _history(RB, range(1, 9), touchdowns=0) + _history(RB, range(9, 13), touchdowns=1) + [_row(RB, 2024, 13)]
    case = _case_for(build_cases(rows, frozenset({2024})), RB, 2024, 13)

    probability = baseline_probability(case)

    assert round(probability, 2) == anytime_td_probability(case.td_seasons, 2024, case.position_td_rate)[0]
    coefficients = NflRedZoneCoefficients(0.1, 0.4, 0.1, 0.4, 0.1)
    assert red_zone_probability(case, coefficients, 0.0) == pytest.approx(probability)


def test_log_loss_and_brier_match_hand_computed_values() -> None:
    probabilities, outcomes = [0.8, 0.3, 0.5], [True, False, True]

    assert log_loss(probabilities, outcomes) == pytest.approx(-(log(0.8) + log(0.7) + log(0.5)) / 3)
    assert brier(probabilities, outcomes) == pytest.approx((0.04 + 0.09 + 0.25) / 3)


def test_log_loss_clips_certain_wrong_predictions_instead_of_failing() -> None:
    assert log_loss([0.0], [True]) == pytest.approx(-log(1e-6))


def test_empty_or_mismatched_scoring_input_is_an_error_not_a_perfect_score() -> None:
    with pytest.raises(ValueError):
        log_loss([], [])
    with pytest.raises(ValueError):
        brier([0.5], [True, False])


def test_score_reports_calibration_per_position() -> None:
    rows = (
        _history(RB, range(1, 5)) + [_row(RB, 2024, 5, touchdowns=1)]
        + [_row(3, 2024, week, position="WR") for week in range(1, 6)]
    )
    cases = build_cases(rows, frozenset({2024}))

    overall = score(cases, lambda case: 0.25)
    by_position = score_by_position(cases, lambda case: 0.25)

    assert (overall.games, overall.mean_predicted, overall.actual_rate) == (2, 0.25, 0.5)
    assert by_position["RB"].actual_rate == 1.0
    assert by_position["WR"].actual_rate == 0.0


TE, WR = 4, 6
SNAP_COEFFICIENTS = {"RB": NflSnapCoefficients(0.05, 0.4), "TE": NflSnapCoefficients(0.02, 0.3)}


def _snap(player: int, season: int, week: int, share: float | None, position: str = "RB") -> NflSnapRow:
    return NflSnapRow(player, position, season, week, share)


def test_snap_evidence_never_uses_the_same_or_a_later_week() -> None:
    rows = _history(RB, range(1, 6))
    snaps = [_snap(RB, 2024, week, 0.5) for week in range(1, 5)] + [_snap(RB, 2024, 5, 1.0), _snap(RB, 2024, 6, 1.0)]

    case = _case_for(build_cases(rows, frozenset({2024}), snaps), RB, 2024, 5)

    assert [(entry.season, entry.games, entry.share) for entry in case.snap_seasons] == [(2024, 4, 0.5)]
    assert case.recent_snap_shares == (0.5, 0.5, 0.5, 0.5)


def test_position_snap_share_excludes_same_week_and_later_games() -> None:
    rows = _history(RB, range(1, 6))
    snaps = (
        [_snap(RB, 2024, week, 0.6) for week in range(1, 5)]
        + [_snap(OTHER_RB, 2024, week, 0.2) for week in range(1, 5)]
        + [_snap(OTHER_RB, 2024, 5, 1.0), _snap(OTHER_RB, 2024, 6, 1.0)]
    )

    case = _case_for(build_cases(rows, frozenset({2024}), snaps), RB, 2024, 5)

    assert case.position_snap_share == pytest.approx(0.4)


def test_a_snap_only_game_adds_snap_evidence_but_no_case_or_td_history() -> None:
    # Week 3 is a blocking game: snaps, no weekly-stat row.
    rows = [_row(TE, 2024, week, position="TE") for week in (1, 2, 4, 5, 6)]
    snaps = [_snap(TE, 2024, week, 0.7, "TE") for week in range(1, 7)]

    cases = build_cases(rows, frozenset({2024}), snaps)

    # Week 5 has only three TD-history games, so week 6 is the only case.
    assert [(c.player_id, c.week) for c in cases] == [(TE, 6)]
    case = cases[0]
    assert case.td_seasons[0].games == 4
    assert case.snap_seasons[0].games == 5


def test_blank_snap_rows_are_not_evidence() -> None:
    rows = _history(RB, range(1, 6))
    snaps = [_snap(RB, 2024, week, None) for week in range(1, 5)]

    case = _case_for(build_cases(rows, frozenset({2024}), snaps), RB, 2024, 5)

    assert case.snap_seasons == []
    assert case.recent_snap_shares == ()


def test_recent_shares_keep_only_the_latest_window_and_cross_seasons() -> None:
    rows = _history(RB, range(1, 17), season=2023) + [_row(RB, 2024, 1)]
    snaps = [_snap(RB, 2023, week, week / 100) for week in range(1, 17)]

    case = _case_for(build_cases(rows, frozenset({2024}), snaps), RB, 2024, 1)

    assert case.recent_snap_shares == (0.13, 0.14, 0.15, 0.16)


def test_snap_form_selects_season_weighted_or_recent_share() -> None:
    rows = _history(RB, range(1, 10))
    snaps = [_snap(RB, 2024, week, 0.2) for week in range(1, 5)] + [_snap(RB, 2024, week, 1.0) for week in range(5, 9)]

    case = _case_for(build_cases(rows, frozenset({2024}), snaps), RB, 2024, 9)

    # Recent: four games at 1.0 plus a 2-game prior at the 0.6 position share.
    assert case_snap_share(case, "recent") == pytest.approx((4 * 1.0 + 2 * 0.6) / 6)
    # Season: eight games averaging 0.6, with the same prior.
    assert case_snap_share(case, "season") == pytest.approx((8 * 0.6 + 2 * 0.6) / 10)


def test_qb_and_wr_snap_probabilities_equal_the_baseline() -> None:
    rows = [_row(WR, 2024, week, position="WR") for week in range(1, 6)] + [_row(7, 2024, w, position="QB") for w in range(1, 6)]
    snaps = [_snap(WR, 2024, week, 1.0, "WR") for week in range(1, 5)] + [_snap(7, 2024, w, 1.0, "QB") for w in range(1, 5)]
    everyone = {**SNAP_COEFFICIENTS, "WR": NflSnapCoefficients(1.0, 1.0), "QB": NflSnapCoefficients(1.0, 1.0)}

    for case in build_cases(rows, frozenset({2024}), snaps):
        assert snap_share_probability(case, everyone, "recent", 0.6) == baseline_probability(case)


def test_rb_and_te_blend_snap_share_and_weight_zero_is_the_baseline() -> None:
    rows = _history(RB, range(1, 6))
    snaps = [_snap(RB, 2024, week, 0.9) for week in range(1, 5)]
    case = _case_for(build_cases(rows, frozenset({2024}), snaps), RB, 2024, 5)

    assert snap_share_probability(case, SNAP_COEFFICIENTS, "season", 0.0) == pytest.approx(baseline_probability(case))
    assert snap_share_probability(case, SNAP_COEFFICIENTS, "season", 0.5) > baseline_probability(case)


def test_implied_total_weight_zero_keeps_the_adopted_production_baseline_and_moneyline() -> None:
    rows = _history(RB, range(1, 6))
    snaps = [_snap(RB, 2024, week, 0.9) for week in range(1, 5)]
    case = _case_for(build_cases(rows, frozenset({2024}), snaps), RB, 2024, 5)

    assert implied_total_probability(case, 23.5, 1.0, 0.0) == pytest.approx(production_probability(case))


def test_end_zone_weight_zero_keeps_the_adopted_production_baseline_and_moneyline() -> None:
    rows = _history(WR, range(1, 6))
    snaps = [_snap(WR, 2024, week, 0.9, "WR") for week in range(1, 5)]
    case = _case_for(build_cases(rows, frozenset({2024}), snaps), WR, 2024, 5)

    assert end_zone_probability(case, NflEndZoneCoefficients(0.1, 0.4), 0.0) == pytest.approx(production_probability(case))


def test_end_zone_history_excludes_the_case_week_and_unloaded_games() -> None:
    rows = [
        *[_row(WR, 2024, week, position="WR", end_zone_targets=1) for week in range(1, 5)],
        _row(WR, 2024, 5, position="WR", end_zone_targets=9),
        _row(WR, 2024, 6, position="WR", end_zone_targets=None),
    ]

    week_five = _case_for(build_cases(rows, frozenset({2024})), WR, 2024, 5)
    week_six = _case_for(build_cases(rows, frozenset({2024})), WR, 2024, 6)

    assert week_five.end_zone_seasons[0].targets_per_game == pytest.approx(1.0)
    # Week 5 is available to week 6, but its own same-week count was not.
    assert week_six.end_zone_seasons[0].targets_per_game == pytest.approx((4 + 9) / 5)


def test_frozen_production_coefficients_cover_exactly_the_backtested_positions() -> None:
    from app.core.nfl_snap_share import SNAP_SHARE_BLEND_WEIGHT, SNAP_SHARE_COEFFICIENTS
    from app.core.nfl_td_backtest import SNAP_SHARE_POSITIONS

    assert set(SNAP_SHARE_COEFFICIENTS) == SNAP_SHARE_POSITIONS
    assert 0.0 < SNAP_SHARE_BLEND_WEIGHT <= 1.0
