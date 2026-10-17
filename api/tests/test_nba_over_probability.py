from datetime import date
from statistics import stdev

import pytest

from app.core import nba_over_probability as rule
from app.core.nba_over_probability import (
    NBA_OVER_PROBABILITY_VERSION, MarketFit, fit_markets, nba_display_verdict, score_cases,
)
from app.core.nba_projection_backtest import NBA_PROJECTION_MODEL_VERSION, NbaReplayCase
from app.core.nfl_over_probability import QUANTILE_LEVELS, ratio_quantiles
from app.core.nfl_over_probability_calibration import CalibrationBin, CalibrationReport


def case(projection: float, actual: float, market: str = "points", player_id: int = 1) -> NbaReplayCase:
    return NbaReplayCase(
        player_id=player_id, game_id=1, game_date=date(2025, 1, 5), game_type="REG", market=market,
        prior_minutes=30.0, projection=projection, actual=actual,
    )


def report(ece: float = 0.01, bins: tuple[CalibrationBin, ...] = (), brier: float = 0.20) -> CalibrationReport:
    return CalibrationReport(n=1000, brier=brier, ece=ece, bins=bins, worst_gap=None)


def test_fit_takes_ratio_quantiles_and_the_error_spread_per_market() -> None:
    cases = [case(20.0, 10.0), case(20.0, 20.0), case(20.0, 30.0), case(4.0, 6.0, market="assists"), case(4.0, 2.0, market="assists")]
    fits = fit_markets(cases)

    assert fits["points"].quantiles == ratio_quantiles([(20.0, 10.0), (20.0, 20.0), (20.0, 30.0)])
    assert len(fits["points"].quantiles) == len(QUANTILE_LEVELS)
    assert fits["points"].sigma == pytest.approx(stdev([-10.0, 0.0, 10.0]))
    assert fits["assists"].sigma == pytest.approx(stdev([2.0, -2.0]))


def test_a_zero_projection_is_skipped_by_the_fit_and_by_scoring() -> None:
    fits = fit_markets([case(0.0, 1.0, market="blocks"), case(0.0, 0.0, market="blocks"), case(10.0, 8.0), case(10.0, 12.0)])

    assert "blocks" not in fits
    blocks_fit = {"blocks": MarketFit(quantiles=tuple(level * 2 for level in QUANTILE_LEVELS), sigma=1.0)}
    assert score_cases(blocks_fit, [case(0.0, 1.0, market="blocks")]) == []


def test_a_market_without_a_fit_is_not_scored() -> None:
    fits = fit_markets([case(10.0, 8.0), case(10.0, 12.0)])
    assert score_cases(fits, [case(3.0, 4.0, market="rebounds")]) == []


def test_each_case_is_scored_at_its_synthetic_lines() -> None:
    fits = fit_markets([case(20.0, actual) for actual in (10.0, 15.0, 20.0, 25.0, 30.0)])
    scored = score_cases(fits, [case(20.0, 21.0)])

    # floor(20 * m) + 0.5 for m in 0.5, 0.75, 1.0, 1.25, 1.5.
    assert [line.line for line in scored] == [10.5, 15.5, 20.5, 25.5, 30.5]
    assert [line.over for line in scored] == [True, True, True, False, False]
    assert all(0.0 <= line.p_over <= 1.0 and 0.0 <= line.normal_p_over <= 1.0 for line in scored)
    assert scored[0].p_over > scored[-1].p_over


def test_verdict_needs_three_hundred_cases() -> None:
    assert nba_display_verdict(299, report(), normal_brier=0.25) == "insufficient"
    assert nba_display_verdict(300, report(), normal_brier=0.25) == "show"


def test_verdict_allows_ece_of_exactly_two_points() -> None:
    assert nba_display_verdict(300, report(ece=0.02), normal_brier=0.25) == "show"
    assert nba_display_verdict(300, report(ece=0.0201), normal_brier=0.25) == "hide"


def test_verdict_checks_only_bins_of_two_hundred_pairs() -> None:
    at_limit = CalibrationBin(n=200, mean_predicted=0.50, observed=0.45)
    too_far = CalibrationBin(n=200, mean_predicted=0.50, observed=0.44)
    small_and_far = CalibrationBin(n=199, mean_predicted=0.90, observed=0.40)

    assert nba_display_verdict(300, report(bins=(at_limit, small_and_far)), normal_brier=0.25) == "show"
    assert nba_display_verdict(300, report(bins=(too_far,)), normal_brier=0.25) == "hide"


def test_verdict_needs_brier_no_worse_than_the_normal() -> None:
    assert nba_display_verdict(300, report(brier=0.20), normal_brier=0.20) == "show"
    assert nba_display_verdict(300, report(brier=0.2001), normal_brier=0.20) == "hide"


def test_the_pre_registered_rule_and_versions_are_pinned() -> None:
    assert (rule.MIN_CASES, rule.MAX_ECE, rule.MAX_BIN_GAP, rule.MIN_BIN_PAIRS) == (300, 0.02, 0.05, 200)
    assert NBA_OVER_PROBABILITY_VERSION == "nba-pover-v1"
    assert NBA_PROJECTION_MODEL_VERSION == "nba-reference-v1"
