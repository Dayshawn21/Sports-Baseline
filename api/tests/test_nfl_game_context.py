import pytest

from app.core.nfl_game_context import (
    SPREAD_FEATURE_NAMES,
    TOTAL_FEATURE_NAMES,
    NflTotalFeatures,
    spread_features,
    total_features,
)


@pytest.mark.parametrize("roof", ["dome", "closed"])
def test_an_indoor_game_ignores_weather_even_when_a_value_is_recorded(roof: str) -> None:
    # One stored closed-roof game carries a temperature; indoors, it cannot matter.
    assert total_features(roof, 20, 30, 7, 7) == NflTotalFeatures(1.0, 0.0, 0.0, 0.0, 0.0)


def test_an_outdoor_game_with_weather_uses_wind_and_cold() -> None:
    # 25 degrees is 15 below the 40-degree cold threshold.
    assert total_features("outdoors", 25, 18, 7, 7) == NflTotalFeatures(0.0, 18.0, 15.0, 0.0, 0.0)


def test_warm_weather_adds_no_cold() -> None:
    assert total_features("outdoors", 75, 11, 7, 7).cold == 0.0


def test_an_open_retractable_roof_plays_as_outdoors() -> None:
    assert total_features("open", 60, 5, 7, 7) == NflTotalFeatures(0.0, 5.0, 0.0, 0.0, 0.0)


@pytest.mark.parametrize(
    "roof, temp, wind",
    [("outdoors", None, 10), ("outdoors", 50, None), ("open", None, None), (None, 50, 10), ("", 50, 10), ("unknown", 50, 10)],
)
def test_unknown_weather_or_roof_is_flagged_rather_than_read_as_calm(roof: str | None, temp: int | None, wind: int | None) -> None:
    assert total_features(roof, temp, wind, 7, 7) == NflTotalFeatures(0.0, 0.0, 0.0, 1.0, 0.0)


@pytest.mark.parametrize("home_rest, away_rest", [(4, 4), (4, 10), (10, 5)])
def test_a_short_week_for_either_team_is_flagged(home_rest: int, away_rest: int) -> None:
    assert total_features("dome", None, None, home_rest, away_rest).short_week == 1.0


@pytest.mark.parametrize("home_rest, away_rest", [(6, 7), (None, None), (None, 7)])
def test_no_short_week_when_both_known_rests_exceed_five_days_or_rest_is_missing(
    home_rest: int | None, away_rest: int | None,
) -> None:
    assert total_features("dome", None, None, home_rest, away_rest).short_week == 0.0


@pytest.mark.parametrize(
    "home_rest, away_rest, diff",
    [(7, 7, 0.0), (14, 4, 7.0), (4, 14, -7.0), (10, 7, 3.0), (None, 7, 0.0), (7, None, 0.0)],
)
def test_rest_difference_is_capped_and_zero_when_unknown(home_rest: int | None, away_rest: int | None, diff: float) -> None:
    assert spread_features(home_rest, away_rest).rest_diff == diff


def test_feature_vectors_follow_the_published_names() -> None:
    assert len(total_features("outdoors", 25, 18, 4, 7).vector()) == len(TOTAL_FEATURE_NAMES)
    assert total_features("outdoors", 25, 18, 4, 7).vector() == [0.0, 18.0, 15.0, 0.0, 1.0]
    assert spread_features(14, 4).vector() == [7.0]
    assert SPREAD_FEATURE_NAMES == ("rest_diff",)
