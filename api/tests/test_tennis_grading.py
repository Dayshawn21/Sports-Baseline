"""Scoring must be exact on hand-worked cases, since every later model decision
reads these numbers."""
from math import log, sqrt

import pytest

from app.core.tennis_grading import (
    calibration_bins,
    clv_summary,
    is_completed_score,
    paired_loss_difference,
    score_component,
)


class TestScoreComponent:
    def test_a_coin_flip_forecast_scores_ln2_and_a_quarter(self):
        score = score_component([0.5, 0.5], [True, False])
        assert score.log_loss == pytest.approx(log(2))
        assert score.brier == pytest.approx(0.25)
        assert (score.n, score.mean_predicted, score.actual_rate) == (2, 0.5, 0.5)

    def test_a_confident_correct_forecast_beats_a_coin_flip(self):
        assert score_component([0.9, 0.1], [True, False]).log_loss < log(2)


class TestPairedLossDifference:
    def test_hand_worked_difference_and_standard_error(self):
        # Match 1: candidate 0.8 vs baseline 0.5, p1 won. Match 2: 0.6 vs 0.5, p1 lost.
        diff = paired_loss_difference([0.8, 0.6], [0.5, 0.5], [True, False])
        d1 = -log(0.8) + log(0.5)
        d2 = -log(0.4) + log(0.5)
        mean = (d1 + d2) / 2
        assert diff.mean == pytest.approx(mean)
        assert diff.standard_error == pytest.approx(sqrt(((d1 - mean) ** 2 + (d2 - mean) ** 2) / 1 / 2))

    def test_negative_means_the_candidate_is_better(self):
        assert paired_loss_difference([0.9, 0.9], [0.6, 0.6], [True, True]).mean < 0

    def test_one_match_has_no_standard_error(self):
        assert paired_loss_difference([0.7], [0.5], [True]).standard_error is None

    def test_mismatched_inputs_are_refused(self):
        with pytest.raises(ValueError):
            paired_loss_difference([0.5], [0.5, 0.5], [True])


class TestCalibrationBins:
    def test_edges_and_the_top_probability(self):
        bins = calibration_bins([0.05, 0.1, 0.95, 1.0], [False, True, True, True])
        assert [(round(b.low, 1), b.n) for b in bins] == [(0.0, 1), (0.1, 1), (0.9, 2)]
        assert bins[-1].actual_rate == 1.0

    def test_empty_bins_are_omitted(self):
        assert len(calibration_bins([0.62, 0.64], [True, False])) == 1


class TestClvSummary:
    def test_toward_away_and_unmoved(self):
        summary = clv_summary([
            (0.60, 0.50, 0.55),   # model above market, market rose: toward
            (0.40, 0.50, 0.53),   # model below market, market rose: away
            (0.60, 0.50, 0.50),   # no move
        ])
        assert (summary.eligible, summary.moved, summary.toward, summary.unmoved) == (3, 2, 1, 1)
        assert summary.toward_rate == pytest.approx(0.5)
        assert summary.mean_move_toward == pytest.approx((0.05 - 0.03 + 0.0) / 3)

    def test_rows_without_a_price_or_a_disagreement_are_not_eligible(self):
        summary = clv_summary([(0.6, None, 0.5), (0.5, 0.5, 0.6), (None, 0.5, 0.6)])
        assert summary.eligible == 0
        assert summary.toward_rate is None

    def test_minimum_gap_keeps_only_real_disagreements(self):
        rows = [(0.52, 0.50, 0.55), (0.60, 0.50, 0.55)]
        assert clv_summary(rows, min_gap=0.03).eligible == 1


class TestIsCompletedScore:
    @pytest.mark.parametrize("score", ["6-4 6-3", "4-6 7-6 7-5", "3-6 6-4 6-2"])
    def test_finished_best_of_three(self, score):
        assert is_completed_score(score)

    @pytest.mark.parametrize("score", ["3-6 3-5", "7-5 2-6 0-0", "", None, "6-4 6-3 4-6", "6-4 6-3 6-2"])
    def test_retirements_walkovers_and_impossible_scores(self, score):
        assert not is_completed_score(score)

    def test_best_of_five_needs_three_sets(self):
        assert is_completed_score("6-4 3-6 6-3 7-6", best_of=5)
        assert not is_completed_score("6-4 6-3", best_of=5)
