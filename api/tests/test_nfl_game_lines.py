import pytest

from app.core.nfl_elo import NFL_ELO_V1
from app.core.nfl_game_lines import (
    PickRecord,
    blend,
    elo_margin,
    game_model_line,
    mae,
    market_home_probability,
    pick_record,
)


def test_elo_margin_is_positive_when_home_is_stronger_matching_the_nflverse_spread_sign() -> None:
    # 50 ELO points plus 25 of home field is three points, like a +3 home spread_line.
    assert elo_margin(1550, 1500, 25) == pytest.approx(3.0)
    assert elo_margin(1450, 1550, 25) == pytest.approx(-3.0)


def test_market_home_probability_removes_the_vig() -> None:
    probability = market_home_probability(-150, 130)

    assert probability is not None
    # Raw implied 0.600 and 0.435 sum past 1; de-vigged they sum to exactly 1.
    assert probability == pytest.approx(0.6 / (0.6 + 100 / 230))


@pytest.mark.parametrize("home, away", [(None, 130), (-150, None), (0, 130)])
def test_market_home_probability_is_none_when_a_price_is_missing(home: int | None, away: int | None) -> None:
    assert market_home_probability(home, away) is None


def test_blend_weight_zero_is_the_market_and_one_is_the_model() -> None:
    assert blend(7.0, 3.0, 0.0) == 3.0
    assert blend(7.0, 3.0, 1.0) == 7.0
    assert blend(7.0, 3.0, 0.25) == pytest.approx(4.0)


def test_mae_averages_absolute_error() -> None:
    assert mae([3.0, -2.0], [7.0, 1.0]) == pytest.approx(3.5)


@pytest.mark.parametrize("predictions, actuals", [([], []), ([1.0], [1.0, 2.0])])
def test_mae_refuses_empty_or_mismatched_inputs(predictions: list[float], actuals: list[float]) -> None:
    with pytest.raises(ValueError):
        mae(predictions, actuals)


def test_spread_pick_hits_when_the_margin_lands_on_the_models_side() -> None:
    # Line: home by 3. Model: home by 7, so it takes the home side.
    record = pick_record([7.0, 7.0, 7.0], [3.0, 3.0, 3.0], [10.0, 1.0, 3.0], threshold=3.0)

    assert record == PickRecord(hits=1, misses=1, pushes=1)
    assert (record.picks, record.hit_rate) == (2, 0.5)


def test_spread_pick_on_the_away_side_hits_when_home_fails_to_cover() -> None:
    # Line: home by 3. Model: away by 1, so it takes the away side (+3).
    assert pick_record([-1.0], [3.0], [-2.0], threshold=3.0) == PickRecord(1, 0, 0)


def test_picks_below_the_threshold_are_not_graded() -> None:
    assert pick_record([4.5], [3.0], [30.0], threshold=3.0) == PickRecord(0, 0, 0)


def test_a_disagreement_a_float_hair_under_the_threshold_still_counts() -> None:
    just_under = 0.3 / 0.1
    assert just_under < 3.0

    assert pick_record([just_under], [0.0], [5.0], threshold=3.0) == PickRecord(1, 0, 0)


def test_total_pick_takes_the_under_when_the_model_is_below_the_line() -> None:
    assert pick_record([41.0], [45.5], [38.0], threshold=3.0) == PickRecord(1, 0, 0)
    assert pick_record([41.0], [45.5], [52.0], threshold=3.0) == PickRecord(0, 1, 0)


def test_hit_rate_is_none_without_decided_picks() -> None:
    assert PickRecord(0, 0, 2).hit_rate is None


def test_a_stronger_home_team_is_favored_with_a_negative_book_spread() -> None:
    line = game_model_line(1600, 1500, 44.0, -200, 170)

    assert line.home_win_probability > 0.5
    # 100 ELO plus 48 of home field is 5.92 points, priced like a -5.92 book spread.
    assert line.home_spread == pytest.approx(-5.92)
    assert line.total == 44.0


def test_a_stronger_away_team_gets_a_positive_home_spread() -> None:
    line = game_model_line(1450, 1600, 41.5, 180, -210)

    assert line.home_win_probability < 0.5
    assert line.home_spread == pytest.approx(4.08)


def test_equal_teams_leave_only_home_field_in_the_spread() -> None:
    line = game_model_line(1500, 1500, 45.0, -110, -110)

    assert line.home_spread == pytest.approx(-NFL_ELO_V1.home_field / 25)
    assert line.home_spread == pytest.approx(-1.92)
    assert line.market_home_win_probability == pytest.approx(0.5)


@pytest.mark.parametrize(("home", "away"), [(None, 150), (-170, None)])
def test_a_missing_moneyline_leaves_the_market_probability_empty(home: int | None, away: int | None) -> None:
    assert game_model_line(1500, 1500, 45.0, home, away).market_home_win_probability is None


def test_the_model_spread_is_the_nflverse_margin_negated() -> None:
    line = game_model_line(1523.4, 1481.9, 44.0, None, None)

    assert line.home_spread == pytest.approx(-elo_margin(1523.4, 1481.9, NFL_ELO_V1.home_field))
