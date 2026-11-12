"""The shared calculator fixture, asserted against app/core.

`web/src/utils/oddsMath.test.ts` reads the same file, so the /tools page and
the API cannot drift apart on the same inputs.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from app.core.kelly import expected_value, kelly_fraction
from app.core.odds import (
    american_to_decimal,
    american_to_prob,
    decimal_to_american,
    implied_prob_from_american,
    overround,
    prob_to_american,
)
from app.core.prizepicks_entry import POWER_PAYOUTS, entry_ev, hit_count_distribution
from app.core.prop_ev import break_even_probability

FIXTURE = Path(__file__).parent / "fixtures" / "calculator_cases.json"

FUNCTIONS: dict[str, Callable[..., object]] = {
    "american_to_prob": american_to_prob,
    "american_to_decimal": american_to_decimal,
    "decimal_to_american": decimal_to_american,
    "prob_to_american": prob_to_american,
    "break_even_probability": break_even_probability,
    "implied_prob_from_american": implied_prob_from_american,
    "overround": overround,
    "expected_value": expected_value,
    "kelly_fraction": kelly_fraction,
}


def _cases() -> list[tuple[str, object, object]]:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return [(name, case["in"], case["out"]) for name, cases in data.items() if name in FUNCTIONS for case in cases]


def test_fixture_covers_every_function() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert set(FUNCTIONS) <= set(data)
    assert all(data[name] for name in FUNCTIONS)


@pytest.mark.parametrize(("name", "args", "expected"), _cases())
def test_core_matches_fixture(name: str, args: object, expected: object) -> None:
    fn = FUNCTIONS[name]
    result = fn(**args) if isinstance(args, dict) else fn(*args)
    if isinstance(expected, int) and not isinstance(expected, bool):
        assert result == expected and isinstance(result, int)
    elif isinstance(expected, list):
        assert list(result) == pytest.approx(expected, abs=1e-9)
    else:
        assert result == pytest.approx(expected, abs=1e-9)


def _fixture(key: str) -> list[dict[str, object]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))[key]


@pytest.mark.parametrize("case", _fixture("entry_ev"))
def test_entry_ev_matches_fixture(case: dict[str, dict[str, object]]) -> None:
    result = entry_ev(case["in"]["probs"], case["in"]["kind"])
    expected = case["out"]
    assert result.distribution == pytest.approx(expected["distribution"], abs=1e-9)
    assert result.expected_multiple == pytest.approx(expected["expected_multiple"], abs=1e-9)
    assert result.ev == pytest.approx(expected["ev"], abs=1e-9)


@pytest.mark.parametrize("case", _fixture("entry_ev_invalid"))
def test_entry_ev_rejects_invalid_entries(case: dict[str, dict[str, object]]) -> None:
    with pytest.raises(ValueError):
        entry_ev(case["in"]["probs"], case["in"]["kind"])


@pytest.mark.parametrize("probs", [[0.6, 0.6], [0.52, 0.58, 0.61, 0.57, 0.66], [1.0, 0.0, 0.3]])
def test_hit_count_distribution_sums_to_one(probs: list[float]) -> None:
    assert sum(hit_count_distribution(probs)) == pytest.approx(1.0, abs=1e-12)
    assert len(hit_count_distribution(probs)) == len(probs) + 1


def test_mixed_legs_are_not_treated_as_equal() -> None:
    mixed = entry_ev([0.4, 0.8], "power").ev
    assert mixed == pytest.approx(0.4 * 0.8 * POWER_PAYOUTS[2] - 1.0)
    assert mixed != pytest.approx(entry_ev([0.6, 0.6], "power").ev)
