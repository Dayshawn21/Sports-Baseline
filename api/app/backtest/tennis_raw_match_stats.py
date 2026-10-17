"""Leakage-safe evaluation helpers for experimental tennis raw-match features.

This module never loads or changes the live predictor.  It compares probability
files created offline, and rejects rows whose feature snapshot is not strictly
older than the match it predicts.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class ValidationExample:
    match_date: date
    feature_as_of: date
    outcome: int
    baseline_probability: float
    candidate_probability: float


@dataclass(frozen=True)
class ProbabilityMetrics:
    brier_score: float
    log_loss: float
    accuracy: float
    calibration_gap: float
    sample_size: int


@dataclass(frozen=True)
class ValidationReport:
    holdout_start: date
    baseline: ProbabilityMetrics
    candidate: ProbabilityMetrics


def _probability(value: float) -> float:
    return min(max(float(value), 0.000001), 0.999999)


def _metrics(probabilities: list[float], outcomes: list[int]) -> ProbabilityMetrics:
    size = len(outcomes)
    if size == 0:
        raise ValueError("The holdout must contain at least one match")
    values = [_probability(value) for value in probabilities]
    brier = sum((probability - outcome) ** 2 for probability, outcome in zip(values, outcomes)) / size
    loss = -sum(
        outcome * math.log(probability) + (1 - outcome) * math.log(1 - probability)
        for probability, outcome in zip(values, outcomes)
    ) / size
    accuracy = sum((probability >= 0.5) == bool(outcome) for probability, outcome in zip(values, outcomes)) / size
    calibration_gap = abs(sum(values) / size - sum(outcomes) / size)
    return ProbabilityMetrics(brier, loss, accuracy, calibration_gap, size)


def evaluate_chronological_holdout(examples: list[ValidationExample], holdout_fraction: float = 0.2) -> ValidationReport:
    """Compare saved baseline and candidate probabilities on the newest matches only."""
    if not 0 < holdout_fraction < 1:
        raise ValueError("holdout_fraction must be between zero and one")
    if len(examples) < 5:
        raise ValueError("At least five completed matches are required for validation")
    if any(example.outcome not in (0, 1) for example in examples):
        raise ValueError("outcome must be 0 or 1")
    if any(example.feature_as_of >= example.match_date for example in examples):
        raise ValueError("feature_as_of must be before the predicted match date")

    ordered = sorted(examples, key=lambda example: example.match_date)
    holdout_count = max(1, math.ceil(len(ordered) * holdout_fraction))
    holdout = ordered[-holdout_count:]
    outcomes = [example.outcome for example in holdout]
    return ValidationReport(
        holdout_start=holdout[0].match_date,
        baseline=_metrics([example.baseline_probability for example in holdout], outcomes),
        candidate=_metrics([example.candidate_probability for example in holdout], outcomes),
    )


def _load_examples(path: Path) -> list[ValidationExample]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Validation input must be a JSON array")
    return [
        ValidationExample(
            match_date=date.fromisoformat(item["match_date"]),
            feature_as_of=date.fromisoformat(item["feature_as_of"]),
            outcome=int(item["outcome"]),
            baseline_probability=float(item["baseline_probability"]),
            candidate_probability=float(item["candidate_probability"]),
        )
        for item in payload
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare tennis raw-stat candidates without touching live predictions")
    parser.add_argument("--input", type=Path, required=True, help="JSON examples with pre-match feature dates")
    parser.add_argument("--holdout-fraction", type=float, default=0.2)
    args = parser.parse_args()
    report = evaluate_chronological_holdout(_load_examples(args.input), args.holdout_fraction)
    print(json.dumps(asdict(report), default=str, indent=2))


if __name__ == "__main__":
    main()
