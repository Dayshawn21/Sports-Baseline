"""The market-anchored blend: market as the anchor, ELO as a log-odds nudge."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from math import exp, log

import pytest

from app.backtest.tennis_closing_lines import ClosingLineCase
from app.backtest.tennis_market_blend import (
    coefficients_for, differences, fitted_prob, live_fitted_prob, live_report, live_rows, report, verdict_h1,
    verdict_h2, verdict_l1,
)
from app.core.tennis_grading import PairedDifference
from app.core.tennis_market_blend import BlendCoefficients, logit, market_anchored_prob
from app.repositories.predictions import GradedPrediction


class TestMarketAnchoredProb:
    def test_unit_market_and_zero_elo_returns_the_market(self):
        assert market_anchored_prob(BlendCoefficients(1.0, 0.0), 0.63, 0.41) == pytest.approx(0.63)

    def test_swapping_players_gives_the_complement(self):
        coefs = BlendCoefficients(0.95, 0.12)
        p = market_anchored_prob(coefs, 0.58, 0.70)
        assert market_anchored_prob(coefs, 0.42, 0.30) == pytest.approx(1 - p)

    def test_missing_elo_returns_the_market(self):
        assert market_anchored_prob(BlendCoefficients(0.9, 0.2), 0.37, None) == 0.37

    def test_hand_worked_case(self):
        z = 0.9 * log(0.6 / 0.4) + 0.2 * log(0.7 / 0.3)
        expected = 1 / (1 + exp(-z))
        assert market_anchored_prob(BlendCoefficients(0.9, 0.2), 0.6, 0.7) == pytest.approx(expected, abs=1e-9)

    @pytest.mark.parametrize("market, elo", [(0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)])
    def test_extreme_inputs_stay_finite_and_clamped(self, market, elo):
        p = market_anchored_prob(BlendCoefficients(5.0, 5.0), market, elo)
        assert 0.01 <= p <= 0.99

    def test_logit_is_finite_at_the_edges(self):
        assert logit(0.0) < 0 < logit(1.0)
        assert logit(0.5) == pytest.approx(0.0)


TABLE = {
    "ATP": BlendCoefficients(1.1, 0.1),
    "WTA": BlendCoefficients(1.3, -0.3),
    "CHALLENGER": BlendCoefficients(1.0, 0.2),
}


def _case(season=2022, *, tour="ATP", category="Main tour", market=0.6, elo=0.7, won=True, reliable=True):
    return ClosingLineCase(
        tour=tour, category=category, round_code=4, tournament="Test Open", season=season,
        match_date=date(season, 6, 1), p1_id=1, p2_id=2, p1_won=won, completed=True, truncated=False,
        elo_prob=elo, market_prob=market, open_prob=market, blend_prob=(0.35 * elo + 0.25 * market) / 0.60,
        p1_close_decimal=1 / market, p2_close_decimal=1 / (1 - market), elo_reliable=reliable,
    )


def _season(season: int) -> list[ClosingLineCase]:
    cases = []
    for i in range(40):
        market, elo = 0.3 + (i % 8) * 0.05, 0.35 + (i % 5) * 0.06
        for tour, category in (("ATP", "Main tour"), ("WTA", "Masters"), ("WTA", "Challenger")):
            cases.append(_case(season, tour=tour, category=category, market=market, elo=elo, won=i % 3 != 0,
                               reliable=i % 4 != 0))
    return cases


class TestGates:
    @pytest.mark.parametrize("mean, se, expected", [
        (-0.0021, 0.001, "pass"), (-0.0020, 0.001, "fail"), (-0.0019, 0.001, "fail"), (0.001, 0.001, "fail"),
    ])
    def test_h1_needs_better_by_more_than_two_se(self, mean, se, expected):
        assert verdict_h1(PairedDifference(100, mean, se)) == expected

    @pytest.mark.parametrize("mean, se, expected", [
        (0.0019, 0.001, "pass"), (0.0020, 0.001, "pass"), (0.0021, 0.001, "fail"), (-0.003, 0.001, "pass"),
    ])
    def test_h2_fails_only_when_worse_by_more_than_two_se(self, mean, se, expected):
        assert verdict_h2(PairedDifference(100, mean, se)) == expected


class TestScoring:
    def test_challenger_cases_take_challenger_coefficients_whatever_the_tour(self):
        assert coefficients_for(_case(tour="WTA", category="Challenger"), TABLE) == TABLE["CHALLENGER"]
        assert coefficients_for(_case(tour="WTA"), TABLE) == TABLE["WTA"]

    def test_gated_cases_score_as_the_close(self):
        case = _case(reliable=False)
        assert fitted_prob(case, TABLE) == case.market_prob
        vs_blend, vs_close = differences([case, replace(case, p1_won=False)], TABLE)
        assert vs_close.mean == pytest.approx(0.0)

    def test_development_report_has_every_section_and_no_holdout(self):
        text = report(_season(2022) + _season(2024), holdout=False, table=TABLE)
        for header in ("IN-SAMPLE", "Frozen coefficients", "Log loss and Brier", "Paired log-loss difference",
                       "Calibration, ATP+WTA", "Flat-stake ROI"):
            assert header in text
        assert "2024" not in text and "Holdout gates" not in text
        assert "ATP+WTA         80" in text

    def test_holdout_report_prints_both_gates_per_verdict_group(self):
        text = report(_season(2022) + _season(2024), holdout=True, table=TABLE)
        assert "HOLDOUT" in text and "Holdout gates" in text
        gate_lines = text.split("Holdout gates")[1].splitlines()[1:]
        assert [line.split()[0] for line in gate_lines] == ["ATP+WTA", "CHALLENGER"]
        assert all("H1 vs hand-set blend" in line and "H2 vs close" in line for line in gate_lines)


T0 = datetime(2026, 9, 1, 12, tzinfo=UTC)


def _row(match_id=1, *, tour="ATP", version="ensemble-v2+lgbm-v6", elo=0.62, market=0.58, ensemble=0.6,
         won=True, completed=True, generated=T0, start=T0 + timedelta(hours=3)) -> GradedPrediction:
    return GradedPrediction(
        match_id=match_id, tour=tour, start_utc=start, generated_at=generated, model_version=version,
        p1_won=won, completed_score=completed, elo_prob=elo, ml_prob=None, market_prob=market,
        ensemble_prob=ensemble, market_book="draftkings", closing_market_prob=market,
    )


class TestLiveGate:
    def test_keeps_every_ensemble_version_and_drops_others(self):
        rows = [_row(1, version="ensemble-v1+lgbm-v5"), _row(2, version="ensemble-v2+lgbm-none"),
                _row(3, version="legacy")]
        assert [r.match_id for r in live_rows(rows)] == [1, 2]

    def test_one_row_per_match_the_latest_pre_start(self):
        early, late = _row(1, generated=T0), _row(1, generated=T0 + timedelta(hours=1), market=0.5)
        after_start = _row(1, generated=T0 + timedelta(hours=4))
        assert live_rows([late, early, after_start]) == [late]

    def test_drops_rows_missing_an_input_or_a_completed_score(self):
        rows = [_row(1, elo=None), _row(2, market=None), _row(3, completed=False), _row(4, tour="ITF"), _row(5)]
        assert [r.match_id for r in live_rows(rows)] == [5]

    def test_a_15_point_gap_serves_the_market(self):
        assert live_fitted_prob(_row(elo=0.80, market=0.60), TABLE) == 0.60
        assert live_fitted_prob(_row(elo=0.66, market=0.60), TABLE) != pytest.approx(0.60)

    @pytest.mark.parametrize("mean, expected", [(0.0020, "pass"), (0.0021, "fail"), (-0.01, "pass")])
    def test_l1_fails_only_when_worse_than_the_market_by_more_than_two_se(self, mean, expected):
        assert verdict_l1(PairedDifference(400, mean, 0.001)) == expected

    def test_live_report_has_a_gate_line_per_verdict_group(self):
        rows = [_row(i, tour=t, won=i % 2 == 0, market=0.4 + i % 5 * 0.05, elo=0.45 + i % 4 * 0.05)
                for i, t in enumerate(["ATP", "WTA", "CHALLENGER"] * 10)]
        text = live_report(rows, TABLE)
        gates = text.split("Live gate")[1].splitlines()[1:]
        assert [g.split()[0] for g in gates] == ["ATP+WTA", "CHALLENGER"]
        assert "ATP+WTA    n=20" in text
