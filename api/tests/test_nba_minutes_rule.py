from datetime import date, timedelta

import pytest

from app.core.nba_minutes_rule import (
    AFFECTED_MINUTES, CANDIDATE_VERSION, COMPARISON_VERSION, DEVELOPMENT_SEASON, FIT_SEASON, FORWARD_MIN_DAYS,
    FORWARD_MIN_PAIRS, OUT_STATUSES,
    ForwardPair, clustered_paired_diff, development_verdict, fixed_sample, forward_verdict, is_affected,
)
from app.core.nba_projection_backtest import MIN_PAIRED_CASES, MIN_RELATIVE_MAE_IMPROVEMENT, STANDARD_ERRORS_REQUIRED
from app.core.nfl_projection_backtest import PairedDiff

FIRST = date(2026, 11, 20)


def test_constants_are_the_pre_registered_values() -> None:
    assert CANDIDATE_VERSION == "nba-minutes-v1" and COMPARISON_VERSION == "nba-reference-v1"
    assert OUT_STATUSES == frozenset({"Out", "Suspension"})
    assert AFFECTED_MINUTES == 1.0
    assert (FIT_SEASON, DEVELOPMENT_SEASON) == (2023, 2024)
    assert (FORWARD_MIN_PAIRS, FORWARD_MIN_DAYS) == (300, 28)
    # Imported from 20f, never copied: a change there would show here.
    assert (MIN_PAIRED_CASES, MIN_RELATIVE_MAE_IMPROVEMENT, STANDARD_ERRORS_REQUIRED) == (300, 0.01, 2.0)


def test_affected_starts_at_one_minute_either_way() -> None:
    assert is_affected(1.0) and is_affected(-1.0) and not is_affected(0.99) and not is_affected(0.0)


def _diff(n: int, change: float, mean_diff: float, se: float) -> PairedDiff:
    return PairedDiff(n=n, production_mae=2.0, variant_mae=2.0 * (1 + change), mean_diff=mean_diff,
                      standard_error=se, relative_mae_change=change)


@pytest.mark.parametrize(("diff", "verdict"), [
    (_diff(299, -0.05, -0.1, 0.01), "insufficient"),
    (_diff(300, -0.05, -0.1, 0.01), "adopt"),
    (_diff(300, -0.009, -0.1, 0.01), "reject"),
    (_diff(300, -0.05, -0.02, 0.01), "reject"),
])
def test_development_gate_is_20fs_rule(diff: PairedDiff, verdict: str) -> None:
    assert development_verdict(diff) == verdict


def _pair(day: int, *, game: int | None = None, change: float = 2.0, cand: float = 1.0, ref: float = 2.0) -> ForwardPair:
    return ForwardPair(game_id=game if game is not None else day, game_date=FIRST + timedelta(days=day),
                       minutes_change=change, candidate_error=cand, reference_error=ref)


def test_clustered_standard_error_matches_a_hand_computed_sample() -> None:
    pairs = [_pair(0, game=1, cand=0.0, ref=1.0), _pair(0, game=1, cand=0.0, ref=1.0),
             _pair(0, game=2, cand=1.0, ref=1.0), _pair(0, game=2, cand=-1.0, ref=1.0)]

    diff = clustered_paired_diff(pairs)

    # diffs -1, -1, 0, 0: mean -0.5; game sums of deviations -1 and +1; sqrt(2/1 * 2) / 4.
    assert diff.mean_diff == -0.5 and diff.standard_error == pytest.approx(0.5)
    assert (diff.production_mae, diff.variant_mae, diff.relative_mae_change) == (1.0, 0.5, -0.5)


def test_the_sample_accrues_until_300_affected_pairs_and_28_settled_days() -> None:
    pairs = [_pair(i // 20) for i in range(299)] + [_pair(0, change=0.5)] * 50

    assert fixed_sample(pairs, FIRST, FIRST + timedelta(days=60)) is None

    pairs.append(_pair(14))
    assert fixed_sample(pairs, FIRST, FIRST + timedelta(days=26)) is None
    sample = fixed_sample(pairs + [_pair(27), _pair(28)], FIRST, FIRST + timedelta(days=27))
    assert sample is not None and len(sample) == 301
    assert all(is_affected(p.minutes_change) for p in sample)


def test_the_sample_ends_on_the_300th_pairs_date_when_that_is_later() -> None:
    pairs = [_pair(i // 5) for i in range(300)] + [_pair(59), _pair(60), _pair(61)]

    sample = fixed_sample(pairs, FIRST, FIRST + timedelta(days=90))

    assert sample is not None and len(sample) == 301 and max(p.game_date for p in sample) == FIRST + timedelta(days=59)


def test_pairs_before_the_first_freeze_never_count() -> None:
    early = [_pair(-1)] * 300
    assert fixed_sample(early, FIRST, FIRST + timedelta(days=90)) is None


def test_forward_verdict_clauses_fail_on_their_own() -> None:
    settled = FIRST + timedelta(days=40)
    better = [_pair(i % 30, game=i, cand=1.0 + (i % 3) * 0.1, ref=2.0) for i in range(300)]
    barely = [_pair(i % 30, game=i, cand=1.995, ref=2.0) for i in range(300)]
    noisy = [_pair(i % 30, game=i // 150, cand=1.0 if i < 150 else 2.9, ref=2.0) for i in range(300)]

    assert forward_verdict(better, FIRST, settled) == "adopt"
    assert forward_verdict(barely, FIRST, settled) == "reject"
    # Better on average, but all the gain sits in one of two games.
    assert forward_verdict(noisy, FIRST, settled) == "reject"
    assert forward_verdict(better[:299], FIRST, settled) == "insufficient"
