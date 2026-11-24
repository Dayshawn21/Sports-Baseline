from dataclasses import replace
from datetime import UTC, date, datetime

from app.core.prop_ranking_rule import SliceResult
from app.core.tennis_prop_adoption import to_payload
from app.core.tennis_prop_check import CheckFunnel, CheckResult, TennisSlice
from app.ingest.tennis_prop_adoption import summary

ACES_ATP = TennisSlice("aces", "ATP", "book", "standard", "over")
REJECTED = TennisSlice("double_faults", "WTA", "model", "standard", "under")


def _result() -> CheckResult:
    return CheckResult(
        slices={
            ACES_ATP: SliceResult(verdict="adopt", n=200, periods=4, hits=140, break_even=0.577),
            REJECTED: SliceResult(verdict="reject", n=200, periods=4, hits=110, break_even=0.577),
        },
        exclusions={}, funnel=CheckFunnel(rows=400, calls=400, picks=400, bets=400), finished_weeks=6,
    )


def _summary(result: CheckResult) -> str:
    return summary(to_payload(result, "props-v3", date(2026, 11, 30), datetime(2026, 11, 30, tzinfo=UTC)))


def test_summary_names_the_rule_version_and_adopted_slices() -> None:
    text = _summary(_result())

    assert "tennis-props-check-v1 on props-v3 (as of 2026-11-30)" in text
    assert "finished weeks 6 | decided slices 2 | adopted 1" in text
    assert "adopt aces / ATP / book / standard / over" in text
    assert "double_faults" not in text
    assert "%" not in text


def test_summary_says_when_nothing_is_adopted() -> None:
    assert "nothing adopted: every line stays gray" in _summary(replace(_result(), slices={}))
