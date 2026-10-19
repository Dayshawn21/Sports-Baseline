from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest

from app.core.nfl_baseline import CURRENT_SEASON, LARGEST_SAMPLE, NO_DATA, PREVIOUS_SEASON
from app.core.nfl_targets_projection import (
    NFL_TARGETS_MODEL_VERSION,
    SELECTED_MONEYLINE_SCALING,
    SELECTED_RECENT_FORM,
    TargetsObservation,
    TargetsProjectionInput,
    prior_targets,
    project_targets,
    valid_target_count,
)


def _history(*values: float | None, season: int = 2024) -> tuple[TargetsObservation, ...]:
    return tuple(
        TargetsObservation(week + season * 100, season, week, None, value)
        for week, value in enumerate(values, start=1)
    )


def _input(*values: float | None) -> TargetsProjectionInput:
    return TargetsProjectionInput(2024, 10, _history(*values), 0.7, True)


def test_candidates_follow_the_exact_formulas_and_default_to_reference() -> None:
    input = _input(0, 2, 4, 6, 8, 10)

    assert project_targets(input).projection == 5.0
    assert project_targets(input, moneyline_scaled=True).projection == 5.4
    assert project_targets(input, recent_form=True).projection == 5.5
    assert project_targets(input, moneyline_scaled=True, recent_form=True).projection == 5.94
    assert NFL_TARGETS_MODEL_VERSION == "nfl-targets-v1"
    assert (SELECTED_MONEYLINE_SCALING, SELECTED_RECENT_FORM) == (False, False)


def test_reference_counts_known_zero_and_qualifies_at_four_observations() -> None:
    result = project_targets(_input(0, 0, 2, 6, None))

    assert result.projection == 2.0
    assert result.games_in_sample == result.recent_games == 4
    assert result.baseline_season == 2024
    assert result.baseline_reason == CURRENT_SEASON
    assert result.quality_flags == ()


@pytest.mark.parametrize("value", [None, -1.0, float("nan"), float("inf"), -float("inf")])
def test_invalid_counts_never_qualify_or_dilute_the_average(value: float | None) -> None:
    result = project_targets(_input(2, 4, 6, value))

    assert not valid_target_count(value)
    assert result.projection is None
    assert result.games_in_sample == 3
    assert result.baseline_reason == LARGEST_SAMPLE
    assert result.quality_flags == ("small_sample",)
    assert project_targets(_input(2, 4, 6, 8, value)).projection == 5.0


def test_no_history_has_an_explicit_no_baseline_result() -> None:
    result = project_targets(_input(None, float("nan")))

    assert result.projection is None
    assert result.baseline_season is None
    assert result.baseline_reason == NO_DATA
    assert result.games_in_sample == result.recent_games == 0
    assert result.quality_flags == ("no_baseline",)


def test_zero_target_baseline_is_a_valid_projection() -> None:
    result = project_targets(_input(0, 0, 0, 0), moneyline_scaled=True, recent_form=True)

    assert valid_target_count(0)
    assert result.projection == 0.0
    assert result.games_in_sample == 4


def test_early_season_uses_older_history_and_recent_form_crosses_seasons() -> None:
    input = TargetsProjectionInput(2024, 3, _history(2, 2, 2, 2, season=2023) + _history(8, 8))
    result = project_targets(input, recent_form=True)

    assert result.baseline_season == 2023
    assert result.baseline_reason == PREVIOUS_SEASON
    assert result.games_in_sample == 4
    assert result.recent_games == 5
    assert result.projection == 3.2
    assert result.quality_flags == ("stale_baseline_season",)


def test_current_season_replaces_older_baseline_at_four_known_counts() -> None:
    input = replace(_input(8, 8, 8, 8), observations=_history(2, 2, 2, 2, 2, season=2023) + _history(8, 8, 8, 8))

    result = project_targets(input)

    assert result.baseline_season == 2024
    assert result.baseline_reason == CURRENT_SEASON
    assert result.projection == 8.0


def test_thin_seasons_cannot_pool_into_four_qualifying_games() -> None:
    input = TargetsProjectionInput(2024, 3, _history(2, 2, 2, season=2023) + _history(8, 8))

    result = project_targets(input, recent_form=True)

    assert result.baseline_season == 2023
    assert result.games_in_sample == 3
    assert result.projection is None


def test_target_week_and_future_history_never_change_either_average() -> None:
    input = replace(_input(2, 4, 6, 8), week=5)
    polluted = replace(input, observations=input.observations + (
        TargetsObservation(900, 2024, 5, datetime(2024, 10, 1, tzinfo=UTC), 100),
        TargetsObservation(901, 2024, 6, None, 100),
        TargetsObservation(902, 2025, 1, None, 100),
    ))

    for recent_form in (False, True):
        assert project_targets(polluted, recent_form=recent_form) == project_targets(input, recent_form=recent_form)
    assert len(prior_targets(polluted)) == 4


def test_recent_order_uses_season_week_kickoff_null_last_and_game_id() -> None:
    earlier = datetime(2024, 10, 6, 17, tzinfo=UTC)
    later = datetime(2024, 10, 6, 20, tzinfo=UTC)
    observations = (
        TargetsObservation(9, 2023, 18, None, 100),
        TargetsObservation(2, 2024, 2, earlier, 2),
        TargetsObservation(99, 2024, 2, None, 99),
        TargetsObservation(3, 2024, 2, later, 3),
        TargetsObservation(4, 2024, 2, later, 4),
        TargetsObservation(1, 2024, 1, later, 1),
    )
    input = TargetsProjectionInput(2024, 3, observations)

    assert [item.game_id for item in prior_targets(input)] == [4, 3, 2, 99, 1, 9]
    assert project_targets(input, recent_form=True).projection == 21.8
    assert prior_targets(replace(input, observations=tuple(reversed(observations)))) == prior_targets(input)


@pytest.mark.parametrize(
    ("probability", "home", "expected"),
    [(0.7, True, 5.4), (0.7, False, 4.6), (0.3, True, 4.6), (0.3, False, 5.4),
     (0.53, True, 5.15), (0.53, False, 4.85), (0.5, True, 5.0)],
)
def test_moneyline_uses_the_players_side_and_caps_both_directions(
    probability: float, home: bool, expected: float,
) -> None:
    input = replace(_input(2, 4, 6, 8), home_market_prob=probability, player_is_home=home)

    assert project_targets(input, moneyline_scaled=True).projection == expected


@pytest.mark.parametrize("probability", [None, 0.0, 1.0, -0.1, 1.1, float("nan"), float("inf")])
def test_missing_or_invalid_probability_keeps_the_case_and_skips_scaling(probability: float | None) -> None:
    input = replace(_input(2, 4, 6, 8), home_market_prob=probability)

    result = project_targets(input, moneyline_scaled=True)

    assert result.projection == 5.0
    assert result.quality_flags == ("market_missing",)
    assert project_targets(input).quality_flags == ()


def test_unknown_side_never_silently_becomes_home_or_away() -> None:
    input = replace(_input(2, 4, 6, 8), player_is_home=None)

    result = project_targets(input, moneyline_scaled=True)

    assert result.projection == 5.0
    assert result.quality_flags == ("team_not_in_game",)
    missing_both = project_targets(replace(input, home_market_prob=None), moneyline_scaled=True)
    assert missing_both.quality_flags == ("market_missing", "team_not_in_game")


def test_rounding_happens_only_after_blending_and_scaling() -> None:
    input = _input(1, 1, 1, 2, 2, 3)

    assert project_targets(input, moneyline_scaled=True, recent_form=True).projection == 1.87


def test_projection_does_not_mutate_its_immutable_input() -> None:
    input = _input(0, 2, 4, 6, 8, 10)
    original = replace(input)

    project_targets(input, moneyline_scaled=True, recent_form=True)

    assert input == original
    with pytest.raises(FrozenInstanceError):
        setattr(input, "week", 11)
    with pytest.raises(FrozenInstanceError):
        setattr(input.observations[0], "targets", 100)


def test_default_projection_is_the_reference_arm_selected_on_2024() -> None:
    # 39a's 2024 run rejected both candidates (moneyline +1.28% MAE, recent form -0.40%).
    input = _input(0, 2, 4, 6, 8, 10)

    assert project_targets(input) == project_targets(input, moneyline_scaled=False, recent_form=False)
    assert project_targets(input) != project_targets(input, moneyline_scaled=True)
    assert project_targets(input) != project_targets(input, recent_form=True)
