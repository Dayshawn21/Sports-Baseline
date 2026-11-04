import datetime as dt
from math import exp, inf

import pytest

from app.core.count_over_probability import NegBinParams, ScaledNormalParams
from app.core import nhl_over_probability_crossfit as crossfit
from app.core.nhl_over_probability import CANDIDATE_ORDER, Family, parity, select_family
from app.core.nhl_over_probability_crossfit import (
    RatioParams, ScoredLine, cross_fit, evaluate, fit_family, read_family, score_half, select_markets, split_by_parity,
)
from app.core.nhl_projection_backtest import NhlReplayCase
from app.nhl.markets import NhlLineOnlyMarket

GOALS = NhlLineOnlyMarket.GOALS


def case(projection: float, actual: float, market: NhlLineOnlyMarket = GOALS, index: int = 0) -> NhlReplayCase:
    return NhlReplayCase(
        player_id=index, game_id=index, game_date=dt.date(2024, 11, 1), game_type="REG", market=market.value,
        prior_toi_minutes=18.0, projection=projection, actual=actual,
    )


def cases(projection: float, actuals: list[float], market: NhlLineOnlyMarket = GOALS) -> list[NhlReplayCase]:
    return [case(projection, actual, market, index) for index, actual in enumerate(actuals)]


def test_negbin_with_poisson_spread_reads_a_poisson_over_probability() -> None:
    params = fit_family("negbin", GOALS, cases(2.0, [1, 3, 2, 2]))
    assert params == NegBinParams(r=inf)
    assert read_family(params, 2.0, 0.5) == pytest.approx(1 - exp(-2.0))


def test_negbin_with_extra_spread_has_a_finite_r() -> None:
    params = fit_family("negbin", GOALS, cases(1.0, [0, 0, 0, 0, 5]))
    assert isinstance(params, NegBinParams) and params.r < inf


def test_scaled_normal_spread_grows_with_the_projection() -> None:
    history = cases(1.0, [2, 0, 2, 0]) + cases(2.0, [4, 0, 4, 0])
    params = fit_family("scaled_normal", GOALS, history)
    assert isinstance(params, ScaledNormalParams) and params.b > 0
    low, high = read_family(params, 1.0, 1.5), read_family(params, 2.0, 2.5)
    assert low is not None and high is not None and high > low


def test_ratio_reads_the_quantiles_of_actual_over_projection() -> None:
    params = fit_family("ratio", GOALS, cases(2.0, [0, 1, 2, 3, 4]))
    assert isinstance(params, RatioParams)
    assert (params.quantiles[0], params.quantiles[20], params.quantiles[-1]) == (0.0, 1.0, 2.0)
    assert read_family(params, 2.0, 2.5) == pytest.approx(0.5, abs=0.15)


@pytest.mark.parametrize("family", CANDIDATE_ORDER)
def test_a_zero_projection_case_is_skipped_by_every_family(family: Family) -> None:
    history = cases(2.0, [1, 3, 2, 2])
    assert fit_family(family, GOALS, history + [case(0.0, 5, index=99)]) == fit_family(family, GOALS, history)


@pytest.mark.parametrize("family", CANDIDATE_ORDER)
def test_fewer_than_two_usable_cases_has_no_fit(family: Family) -> None:
    assert fit_family(family, GOALS, cases(2.0, [1])) is None
    assert fit_family(family, GOALS, [case(0.0, 1, index=1), case(0.0, 2, index=2), case(2.0, 1, index=3)]) is None


@pytest.mark.parametrize(("family", "market", "fits"), [
    ("negbin", NhlLineOnlyMarket.PLUS_MINUS, False),
    ("negbin", NhlLineOnlyMarket.TIME_ON_ICE, False),
    ("ratio", NhlLineOnlyMarket.PLUS_MINUS, False),
    ("ratio", NhlLineOnlyMarket.TIME_ON_ICE, True),
    ("scaled_normal", NhlLineOnlyMarket.PLUS_MINUS, True),
    ("negbin", NhlLineOnlyMarket.HITS, True),
])
def test_a_market_outside_a_familys_domain_has_no_fit(family: Family, market: NhlLineOnlyMarket, fits: bool) -> None:
    assert (fit_family(family, market, cases(2.0, [1, 3, 2, 2], market)) is not None) is fits


@pytest.mark.parametrize("family", CANDIDATE_ORDER)
def test_a_whole_number_line_reads_none_for_every_family(family: Family) -> None:
    params = fit_family(family, GOALS, cases(2.0, [1, 3, 2, 2, 0, 4]))
    assert params is not None
    assert read_family(params, 2.0, 2.0) is None
    assert read_family(params, 2.0, 2.5) is not None


def poisson_actuals(mean: float, n: int) -> list[float]:
    """A stratified Poisson sample: the quantile at each of n evenly spaced probabilities."""
    actuals, k, mass = [], 0, exp(-mean)
    cumulative = mass
    for i in range(n):
        level = (i + 0.5) / n
        while cumulative < level:
            k += 1
            mass *= mean / k
            cumulative += mass
        actuals.append(float(k))
    return actuals


def weekly_cases(mean: float, n: int, market: NhlLineOnlyMarket = GOALS) -> list[NhlReplayCase]:
    """One case per week, so ISO-week parity alternates case by case."""
    return [
        NhlReplayCase(
            player_id=index, game_id=index, game_date=dt.date(2024, 10, 7) + dt.timedelta(days=7 * index),
            game_type="REG", market=market.value, prior_toi_minutes=18.0, projection=mean, actual=actual,
        )
        for index, actual in enumerate(poisson_actuals(mean, n))
    ]


def test_a_case_is_never_scored_by_a_fit_that_contains_it(monkeypatch: pytest.MonkeyPatch) -> None:
    history = weekly_cases(2.0, 40)
    fit_parities: list[set[int]] = []
    scored_parities: list[set[int]] = []
    original_fit, original_score = crossfit.fit_market, crossfit.score_cases

    def recording_fit(family, market, cases):  # type: ignore[no-untyped-def]
        cases = list(cases)
        fit_parities.append({parity(c.game_date) for c in cases})
        return original_fit(family, market, cases)

    def recording_score(fit, cases):  # type: ignore[no-untyped-def]
        cases = list(cases)
        scored_parities.append({parity(c.game_date) for c in cases})
        return original_score(fit, cases)

    monkeypatch.setattr(crossfit, "fit_market", recording_fit)
    monkeypatch.setattr(crossfit, "score_cases", recording_score)
    cross_fit("negbin", history)
    assert len(fit_parities) == len(scored_parities) == 2
    for fitted, scored in zip(fit_parities, scored_parities, strict=True):
        assert len(fitted) == 1 and len(scored) == 1 and fitted.isdisjoint(scored)


def test_both_halves_are_scored() -> None:
    lines = cross_fit("negbin", weekly_cases(2.0, 40))
    assert {parity(line.case.game_date) for line in lines} == {0, 1}
    even, odd = split_by_parity(weekly_cases(2.0, 40))
    assert len(even) == len(odd) == 20
    assert {line.case.key for line in score_half("negbin", even, odd)}.isdisjoint({c.key for c in even})


def test_a_half_with_no_fit_scores_nothing() -> None:
    even, odd = split_by_parity(weekly_cases(2.0, 40))
    assert score_half("negbin", [], odd) == []
    assert score_half("negbin", even[:1], odd) == []


def scored(p_over: float, over: bool, index: int, normal: float = 0.5) -> ScoredLine:
    history = case(2.0, 3 if over else 1, index=index)
    return ScoredLine(case=history, line=2.5, p_over=p_over, normal_p_over=normal, over=over)


def test_evaluate_shows_a_calibrated_family_that_beats_the_normal() -> None:
    lines = [scored(0.5, over=index % 2 == 0, index=index, normal=0.9) for index in range(400)]
    result = evaluate("negbin", lines)
    assert (result.cases, result.verdict) == (400, "show")
    assert result.brier == pytest.approx(0.25)


def test_evaluate_hides_a_miscalibrated_family() -> None:
    lines = [scored(0.9, over=index % 2 == 0, index=index, normal=0.9) for index in range(400)]
    assert evaluate("ratio", lines).verdict == "hide"


def test_evaluate_is_insufficient_under_three_hundred_cases_and_for_no_lines() -> None:
    assert evaluate("negbin", [scored(0.5, index % 2 == 0, index) for index in range(299)]).verdict == "insufficient"
    empty = evaluate("negbin", [])
    assert (empty.cases, empty.verdict) == (0, "insufficient") and empty.brier == inf


def test_selection_picks_a_family_for_a_well_fitted_market_and_lists_only_applicable_families() -> None:
    selections = select_markets(weekly_cases(2.0, 800))
    goals = selections[GOALS]
    assert [result.family for result in goals.results] == list(CANDIDATE_ORDER)
    assert goals.selected == select_family(goals.results) and goals.selected is not None
    assert all(result.cases > 300 for result in goals.results if result.verdict == "show")


def test_a_market_with_too_few_cases_is_hidden_and_never_selected() -> None:
    selection = select_markets(weekly_cases(2.0, 40))[GOALS]
    assert selection.selected is None
    assert {result.verdict for result in selection.results} == {"insufficient"}


def test_plus_minus_has_only_the_scaled_normal_candidate() -> None:
    selection = select_markets(weekly_cases(2.0, 40, NhlLineOnlyMarket.PLUS_MINUS))[NhlLineOnlyMarket.PLUS_MINUS]
    assert [result.family for result in selection.results] == ["scaled_normal"]
