from datetime import date, timedelta

import pytest

from app.backtest.tennis_raw_match_stats import ValidationExample, evaluate_chronological_holdout


def _examples() -> list[ValidationExample]:
    start = date(2026, 1, 1)
    return [
        ValidationExample(
            match_date=start + timedelta(days=index),
            feature_as_of=start + timedelta(days=index - 1),
            outcome=index % 2,
            baseline_probability=0.5,
            candidate_probability=0.8 if index % 2 else 0.2,
        )
        for index in range(10)
    ]


def test_validation_uses_only_the_newest_chronological_holdout():
    report = evaluate_chronological_holdout(_examples(), holdout_fraction=0.2)

    assert report.holdout_start == date(2026, 1, 9)
    assert report.baseline.sample_size == 2
    assert report.candidate.accuracy == 1.0
    assert report.candidate.brier_score < report.baseline.brier_score


def test_validation_rejects_future_information():
    examples = _examples()
    invalid = ValidationExample(
        match_date=examples[0].match_date,
        feature_as_of=examples[0].match_date,
        outcome=examples[0].outcome,
        baseline_probability=examples[0].baseline_probability,
        candidate_probability=examples[0].candidate_probability,
    )

    with pytest.raises(ValueError, match="feature_as_of"):
        evaluate_chronological_holdout([invalid, *examples[1:]])
