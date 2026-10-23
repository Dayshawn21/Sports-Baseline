import datetime as dt
import random

import pytest

from app.core import nba_over_probability_v2 as pre_registration
from app.core import nba_over_probability_v2_fit as frozen_fit
from app.core.count_over_probability import NegBinParams, ScaledNormalParams
from app.core.nba_over_probability_v2_confirmation_score import (
    evaluate_markets,
    family_of,
    gate,
    normal_sigmas,
    parameter_drift,
    push_context,
    refit,
    sample_cases,
    score_sample,
)
from app.core.nba_projection_backtest import NbaReplayCase
from app.core.nfl_over_probability_calibration import normal_over_probability

DAY = dt.date(2026, 10, 21)


def _case(game_id=1, market="points", projection=20.0, actual=18.0, game_type="REG", player_id=1):
    return NbaReplayCase(
        player_id=player_id, game_id=game_id, game_date=DAY, game_type=game_type,
        market=market, prior_minutes=30.0, projection=projection, actual=actual,
    )


def test_fit_module_confirmation_sample_matches_pre_registration():
    assert frozen_fit.CONFIRMATION_SEASON == pre_registration.CONFIRMATION_SEASON
    assert frozen_fit.CONFIRMATION_WEEKS == pre_registration.CONFIRMATION_WEEKS


def test_gate_needs_every_confirmation_week_finished():
    assert gate({1, 2, 3}) == "accruing"
    assert gate(set()) == "accruing"
    assert gate({1, 2, 3, 4, 5}) == "ready"


def test_sample_keeps_only_reg_cases_in_weeks_1_to_4_carried_markets_positive_projection():
    week_by_game = {1: 1, 4: 4, 5: 5}
    kept = _case(game_id=4)
    cases = [
        kept,
        _case(game_id=5),
        _case(game_id=99),
        _case(game_id=1, game_type="PIN"),
        _case(game_id=1, market="blocks"),
        _case(game_id=1, projection=0.0),
    ]
    assert sample_cases(cases, week_by_game, {"points", "rebounds"}) == [kept]


def test_normal_sigma_comes_from_fit_cases_only():
    fit_cases = [_case(projection=20, actual=a) for a in (10, 30, 10, 30)]
    scored_cases = [_case(projection=20, actual=20) for _ in range(4)]
    sigmas = normal_sigmas(fit_cases, {"points"})
    lines = score_sample({"points": ScaledNormalParams(a=10.0, b=1.0)}, sigmas, scored_cases)
    assert round(sigmas["points"], 6) == round(11.547005383792516, 6)
    assert lines
    assert all(line.normal_p_over == normal_over_probability(20, sigmas["points"], line.line) for line in lines)
    assert normal_sigmas(scored_cases, {"points"})["points"] == 0


def test_scoring_reads_only_the_frozen_params():
    frozen = {"points": ScaledNormalParams(a=14.0, b=2.0)}
    other = {"points": ScaledNormalParams(a=40.0, b=0.5)}
    cases = [_case(projection=22.0, actual=25.0)]
    first = score_sample(frozen, {"points": 7.0}, cases)
    assert [line.p_over for line in first] != [line.p_over for line in score_sample(other, {"points": 7.0}, cases)]
    # A different refit only shows up as drift; it never changes what is scored.
    assert [d.market for d in parameter_drift(frozen, other)] == ["points"]
    assert [line.p_over for line in score_sample(frozen, {"points": 7.0}, cases)] == [line.p_over for line in first]


def test_drift_is_empty_when_refit_reproduces_frozen_params():
    rng = random.Random(7)
    fit_cases = [_case(player_id=i, market="rebounds", projection=8.0, actual=float(rng.randint(2, 15))) for i in range(500)]
    fit_cases += [_case(player_id=i, projection=20.0, actual=rng.gauss(20, 6)) for i in range(500)]
    shape = {"rebounds": NegBinParams(r=10.0), "points": ScaledNormalParams(a=1.0, b=1.0)}
    frozen = refit(shape, fit_cases)
    assert parameter_drift(frozen, refit(frozen, fit_cases)) == []
    assert family_of(frozen["rebounds"]) == "negbin"
    assert family_of(frozen["points"]) == "scaled_normal"


def test_drift_flags_family_change_and_missing_market():
    frozen = {"rebounds": NegBinParams(r=10.0), "points": ScaledNormalParams(a=1.0, b=1.0)}
    drift = parameter_drift(frozen, {"rebounds": ScaledNormalParams(a=1.0, b=1.0)})
    assert [d.market for d in drift] == ["rebounds", "points"]
    assert drift[1].refit is None


def test_evaluate_markets_reports_each_scored_carried_market():
    rng = random.Random(11)
    frozen = {"points": ScaledNormalParams(a=0.0, b=1.0), "rebounds": NegBinParams(r=15.0)}
    cases = [_case(player_id=i, projection=20.0, actual=float(round(rng.gauss(20, 4.5)))) for i in range(400)]
    lines = score_sample(frozen, {"points": 4.5, "rebounds": 3.0}, cases)
    results = evaluate_markets(frozen, lines)
    assert set(results) == {"points"}
    assert results["points"].family == "scaled_normal"
    assert results["points"].cases == 400
    assert results["points"].pairs == len(lines)
    expected_normal = sum((line.normal_p_over - line.over) ** 2 for line in lines) / len(lines)
    assert results["points"].normal_brier == pytest.approx(expected_normal)


def test_push_context_uses_whole_number_lines():
    frozen = {"rebounds": NegBinParams(r=15.0)}
    cases = [_case(market="rebounds", projection=8.0, actual=7.0)]
    context = push_context(frozen, cases)["rebounds"]
    assert context.pairs >= 1
    assert 0 < context.predicted < 1
