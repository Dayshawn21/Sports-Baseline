from dataclasses import replace
from math import sqrt

import pytest

from app.core.nfl_projection_backtest import (
    MIN_PAIRED_CASES, PairedDiff, ReplayCase, adoption_verdict, market_metrics, paired,
)


def _case(player_id: int, projection: float, actual: float, game_id: int = 7) -> ReplayCase:
    return ReplayCase(
        player_id=player_id, game_id=game_id, week=10, position="WR", market="receptions",
        projection=projection, actual=actual,
    )


def _diff(**overrides: float) -> PairedDiff:
    base = PairedDiff(
        n=MIN_PAIRED_CASES, production_mae=10.0, variant_mae=9.0, mean_diff=-1.0,
        standard_error=0.1, relative_mae_change=-0.1,
    )
    return replace(base, **overrides)


def test_market_metrics_scores_error_bias_and_share_below() -> None:
    cases = [_case(1, 7, 5), _case(2, 4, 5), _case(3, 6, 6), _case(4, 8, 5)]

    metrics = market_metrics(cases)

    assert metrics.n == 4
    assert metrics.mae == pytest.approx(1.5)
    assert metrics.rmse == pytest.approx(sqrt(3.5))
    assert metrics.bias == pytest.approx(1.0)
    assert metrics.share_below == pytest.approx(2 / 3)


def test_share_below_excludes_exact_ties_and_is_none_when_all_tie() -> None:
    assert market_metrics([_case(1, 5, 4), _case(2, 5, 5)]).share_below == 1.0
    assert market_metrics([_case(1, 5, 5)]).share_below is None


def test_market_metrics_rejects_an_empty_market() -> None:
    with pytest.raises(ValueError):
        market_metrics([])


def test_paired_matches_on_player_game_and_market_and_drops_the_rest() -> None:
    production = [_case(1, 7, 5), _case(2, 3, 5), _case(3, 6, 5), _case(4, 9, 5)]
    variant = [_case(1, 6, 5), _case(2, 3, 5), _case(3, 5, 5), _case(3, 9, 5, game_id=8)]

    diff = paired(production, variant)

    assert diff.n == 3
    assert diff.production_mae == pytest.approx(5 / 3)
    assert diff.variant_mae == pytest.approx(1.0)
    assert diff.mean_diff == pytest.approx(-2 / 3)
    assert diff.standard_error == pytest.approx(1 / 3)
    assert diff.relative_mae_change == pytest.approx(-0.4)


def test_paired_rejects_no_matches() -> None:
    with pytest.raises(ValueError):
        paired([_case(1, 7, 5)], [_case(2, 7, 5)])


def test_a_clear_improvement_on_enough_cases_is_adopted() -> None:
    assert adoption_verdict(_diff()) == "adopt"


def test_fewer_than_the_minimum_cases_is_insufficient() -> None:
    assert adoption_verdict(_diff(n=MIN_PAIRED_CASES - 1)) == "insufficient"


def test_exactly_one_percent_improvement_passes_and_just_under_rejects() -> None:
    assert adoption_verdict(_diff(relative_mae_change=-0.01)) == "adopt"
    assert adoption_verdict(_diff(relative_mae_change=-0.0099)) == "reject"


def test_exactly_two_standard_errors_rejects_and_just_beyond_passes() -> None:
    assert adoption_verdict(_diff(mean_diff=-0.2, standard_error=0.1)) == "reject"
    assert adoption_verdict(_diff(mean_diff=-0.2001, standard_error=0.1)) == "adopt"


def test_a_worse_variant_is_rejected() -> None:
    assert adoption_verdict(_diff(mean_diff=0.5, relative_mae_change=0.05)) == "reject"
