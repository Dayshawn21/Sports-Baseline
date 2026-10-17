"""The 26d fit: recovers known coefficients, never sees the holdout, renders a valid module."""

import random
from datetime import date
from math import exp

import pytest

from app.backtest.tennis_closing_lines import ClosingLineCase
from app.backtest.tennis_market_blend_fit import (
    FitResult, development_cases, fit_group, in_group, render_module, served_prob,
)
from app.core.tennis_market_blend import BlendCoefficients, logit


def _case(market: float, elo: float, won: bool, *, season: int = 2022, tour: str = "ATP",
          category: str = "Main tour", reliable: bool = True) -> ClosingLineCase:
    return ClosingLineCase(
        tour=tour, category=category, round_code=4, tournament="Test Open", season=season,
        match_date=date(season, 6, 1), p1_id=1, p2_id=2, p1_won=won, completed=True, truncated=False,
        elo_prob=elo, market_prob=market, open_prob=market, blend_prob=(0.35 * elo + 0.25 * market) / 0.60,
        p1_close_decimal=1 / market, p2_close_decimal=1 / (1 - market), elo_reliable=reliable,
    )


def _synthetic(a: float, b: float, n: int, seed: int = 7, season: int = 2022) -> list[ClosingLineCase]:
    rng = random.Random(seed)
    cases = []
    for _ in range(n):
        market, elo = rng.uniform(0.15, 0.85), rng.uniform(0.15, 0.85)
        z = a * logit(market) + b * logit(elo)
        cases.append(_case(market, elo, rng.random() < 1 / (1 + exp(-z)), season=season))
    return cases


def test_fit_recovers_known_coefficients():
    fit = fit_group(_synthetic(0.9, 0.3, 20000))
    assert abs(fit.coefficients.market - 0.9) < 3 * fit.market_se
    assert abs(fit.coefficients.elo - 0.3) < 3 * fit.elo_se


def test_holdout_seasons_never_reach_the_fit():
    development = _synthetic(0.9, 0.3, 3000)
    poisoned = development + [_case(0.9, 0.9, False, season=2024) for _ in range(3000)]
    assert fit_group(poisoned) == fit_group(development)
    assert all(c.season == 2022 for c in development_cases(poisoned, "ATP"))


def test_unreliable_elo_cases_are_not_fitted():
    development = _synthetic(0.9, 0.3, 3000)
    gated = [_case(0.9, 0.9, False, reliable=False) for _ in range(500)]
    assert fit_group(development + gated) == fit_group(development)


def test_too_few_cases_raises():
    with pytest.raises(ValueError):
        fit_group([_case(0.6, 0.6, True)])


def test_groups_follow_26cs_scored_and_challenger_sets():
    assert in_group(_case(0.6, 0.6, True, tour="WTA"), "WTA")
    assert not in_group(_case(0.6, 0.6, True, tour="WTA"), "ATP")
    assert in_group(_case(0.6, 0.6, True, tour="WTA", category="Challenger"), "CHALLENGER")
    assert not in_group(_case(0.6, 0.6, True, category="Challenger"), "ATP")


def test_served_prob_is_the_market_when_elo_is_gated():
    coefs = BlendCoefficients(0.9, 0.4)
    assert served_prob(_case(0.62, 0.8, True, reliable=False), coefs) == 0.62
    assert served_prob(_case(0.62, 0.8, True), coefs) != pytest.approx(0.62)


def test_rendered_module_round_trips():
    fits = {g: FitResult(100, BlendCoefficients(0.98 + i / 100, 0.05 - i / 100), 0.01, 0.02)
            for i, g in enumerate(("ATP", "CHALLENGER", "WTA"))}
    namespace: dict[str, object] = {}
    exec(render_module(fits), namespace)
    assert namespace["FIT_SEASONS"] == (2022,)
    assert namespace["FIT_COEFFICIENTS"]["WTA"] == BlendCoefficients(1.0, 0.03)
    assert namespace["FIT_SIZES"] == {"ATP": 100, "CHALLENGER": 100, "WTA": 100}
