from dataclasses import replace

import pytest

from app.core.nfl_over_probability_calibration import (
    MAX_BIN_GAP, MAX_ECE, MIN_BIN_PAIRS, MIN_CASES, CalibrationPair, CalibrationReport, calibrate,
    display_verdict, normal_over_probability, synthetic_lines,
)


def test_synthetic_lines_snap_to_half_points() -> None:
    assert synthetic_lines(60.0) == (30.5, 45.5, 60.5, 75.5, 90.5)


def test_synthetic_lines_drop_duplicates_under_one() -> None:
    assert synthetic_lines(0.8) == (0.5, 1.5)


def test_synthetic_lines_drop_non_positive_lines() -> None:
    assert synthetic_lines(-2.0) == ()


def test_calibrate_scores_brier_ece_and_bins() -> None:
    pairs = [CalibrationPair(0.2, False), CalibrationPair(0.2, True), CalibrationPair(0.8, True), CalibrationPair(0.8, True)]

    report = calibrate(pairs)

    assert report.n == 4
    assert report.brier == pytest.approx((0.04 + 0.64 + 0.04 + 0.04) / 4)
    # Low bin: predicted 0.2, observed 0.5. High bin: predicted 0.8, observed 1.0.
    assert report.ece == pytest.approx((2 * 0.3 + 2 * 0.2) / 4)
    assert [(b.n, b.observed) for b in report.bins] == [(2, 0.5), (2, 1.0)]
    assert report.worst_gap is None


def test_a_prediction_of_one_lands_in_the_top_bin() -> None:
    report = calibrate([CalibrationPair(1.0, True), CalibrationPair(0.95, True)])

    assert len(report.bins) == 1


def test_worst_gap_reads_only_bins_with_enough_pairs() -> None:
    big = [CalibrationPair(0.5, i % 2 == 0) for i in range(MIN_BIN_PAIRS)]
    small = [CalibrationPair(0.9, False)] * (MIN_BIN_PAIRS - 1)

    report = calibrate(big + small)

    assert report.worst_gap == pytest.approx(0.0)


def test_calibrate_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        calibrate([])


def test_normal_baseline_is_even_at_the_projection_and_falls_above() -> None:
    assert normal_over_probability(50.0, 10.0, 50.0) == pytest.approx(0.5)
    assert normal_over_probability(50.0, 10.0, 60.0) == pytest.approx(0.1587, abs=1e-4)
    with pytest.raises(ValueError):
        normal_over_probability(50.0, 0.0, 50.0)


PASSING = CalibrationReport(n=1500, brier=0.20, ece=MAX_ECE, bins=(), worst_gap=MAX_BIN_GAP)


def test_verdict_shows_at_every_boundary() -> None:
    assert display_verdict(MIN_CASES, PASSING, normal_brier=0.20) == "show"


def test_verdict_is_insufficient_below_the_minimum() -> None:
    assert display_verdict(MIN_CASES - 1, PASSING, normal_brier=0.25) == "insufficient"


@pytest.mark.parametrize("change", [
    {"ece": MAX_ECE + 0.0001},
    {"worst_gap": MAX_BIN_GAP + 0.0001},
    {"brier": 0.2001},
])
def test_verdict_hides_past_any_boundary(change: dict[str, float]) -> None:
    assert display_verdict(MIN_CASES, replace(PASSING, **change), normal_brier=0.20) == "hide"


def test_verdict_shows_when_no_bin_is_large_enough_to_judge() -> None:
    assert display_verdict(MIN_CASES, replace(PASSING, worst_gap=None), normal_brier=0.20) == "show"
