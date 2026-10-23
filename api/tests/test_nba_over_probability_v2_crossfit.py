import datetime as dt

import numpy as np

from app.core import nba_over_probability_v2_crossfit as crossfit
from app.core.nba_over_probability_v2 import CandidateResult, parity, select_family
from app.core.nba_projection_backtest import NbaReplayCase

SEASON_START = dt.date(2024, 10, 21)


def _cases(market, means, actuals):
    return [
        NbaReplayCase(
            player_id=i, game_id=i, game_date=SEASON_START + dt.timedelta(days=i % 160), game_type="REG",
            market=market, prior_minutes=30.0, projection=float(mean), actual=float(actual),
        )
        for i, (mean, actual) in enumerate(zip(means, actuals))
    ]


def _evaluate_all(cases, market):
    results = []
    for family in ("negbin", "scaled_normal"):
        lines = [line for line in crossfit.cross_fit(family, cases) if line.case.market == market]
        results.append(crossfit.evaluate(family, lines))
    return results


def test_overdispersed_small_counts_select_negbin_and_hide_the_normal():
    rng = np.random.default_rng(7)
    means = rng.uniform(0.4, 2.5, 8000)
    cases = _cases("blocks", means, rng.negative_binomial(1.5, 1.5 / (1.5 + means)))
    by_family = {result.family: result for result in _evaluate_all(cases, "blocks")}
    assert by_family["negbin"].verdict == "show"
    assert by_family["scaled_normal"].verdict == "hide"
    assert select_family(list(by_family.values())) == "negbin"


def test_a_badly_centered_market_is_not_carried():
    # Actuals run at twice the projection, which no mean-anchored family fixes.
    rng = np.random.default_rng(8)
    means = rng.uniform(4.0, 12.0, 6000)
    cases = _cases("rebounds", means, rng.poisson(2.0 * means))
    assert select_family(_evaluate_all(cases, "rebounds")) is None


def test_no_case_is_scored_by_a_fit_that_includes_it(monkeypatch):
    calls = []
    original = crossfit.score_half

    def spy(family, fit_cases, score_cases):
        fit_cases, score_cases = list(fit_cases), list(score_cases)
        calls.append(({parity(c) for c in fit_cases}, {parity(c) for c in score_cases}))
        return original(family, fit_cases, score_cases)

    monkeypatch.setattr(crossfit, "score_half", spy)
    rng = np.random.default_rng(9)
    means = rng.uniform(5.0, 25.0, 400)
    crossfit.cross_fit("negbin", _cases("points", means, rng.poisson(means)))
    assert calls == [({0}, {1}), ({1}, {0})]


def test_non_target_markets_are_ignored():
    rng = np.random.default_rng(10)
    means = rng.uniform(2.0, 8.0, 400)
    assert crossfit.cross_fit("negbin", _cases("assists", means, rng.poisson(means))) == []


def test_half_lines_only_and_normal_baseline_present():
    rng = np.random.default_rng(11)
    means = rng.uniform(5.0, 25.0, 400)
    lines = crossfit.cross_fit("scaled_normal", _cases("points", means, rng.poisson(means)))
    assert lines and all(line.line % 1 == 0.5 for line in lines)
    assert all(0.0 <= line.normal_p_over <= 1.0 for line in lines)


def test_evaluate_counts_distinct_cases():
    rng = np.random.default_rng(12)
    means = rng.uniform(5.0, 25.0, 100)
    lines = crossfit.cross_fit("negbin", _cases("points", means, rng.poisson(means)))
    result = crossfit.evaluate("negbin", lines)
    assert isinstance(result, CandidateResult)
    assert result.cases == 100
    assert result.verdict == "insufficient"
