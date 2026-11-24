import sys

import pytest

from app.backtest import nfl_usage_shift
from app.backtest.nfl_usage_shift import count_report, development_report, holdout_report, season_error
from app.core.nfl_projection_backtest import ReplayCase


def _case(player_id: int, market: str, projection: float, shifted: bool = False) -> ReplayCase:
    return ReplayCase(player_id, 10, 5, "RB", market, projection, 50.0, shifted)


def _development_cases() -> dict[str, list[ReplayCase]]:
    # Player 1 is shifted in receptions; player 2 is not, so he never enters the table.
    return {
        "production": [_case(1, "receptions", 40.0), _case(2, "receptions", 40.0)],
        "usage_shift_t05": [_case(1, "receptions", 45.0, True), _case(2, "receptions", 40.0)],
        "usage_shift_t10": [_case(1, "receptions", 52.0, True), _case(2, "receptions", 40.0)],
    }


def test_development_report_tables_shifted_mae_and_the_pick() -> None:
    text = development_report(_development_cases())

    receptions = next(line for line in text.splitlines() if line.strip().startswith("receptions"))
    # Production misses by 10, t 0.5 by 5, t 1 by 2: pick 1.
    assert receptions.split() == ["receptions", "1", "10.000", "5.000", "2.000", "1"]
    assert "no shifted rows; pick 0" in next(line for line in text.splitlines() if "rushing_yards" in line)
    assert "Rule pre-registered in commit a0941c328d1f14651a88842cbd1db8af0c1a878d." in text


def test_holdout_report_gives_a_verdict_only_for_candidates() -> None:
    cases = {
        "production": [_case(1, "receptions", 40.0), _case(3, "rushing_yards", 40.0)],
        "usage_shift": [_case(1, "receptions", 52.0, True), _case(3, "rushing_yards", 45.0, True)],
    }

    text = holdout_report(cases, {"receptions": 1.0, "rushing_yards": 0.0})

    assert "insufficient" in next(line for line in text.splitlines() if line.strip().startswith("receptions"))
    assert "not a candidate" in next(line for line in text.splitlines() if "rushing_yards" in line)


@pytest.mark.parametrize(("season", "holdout", "picks", "allowed"), [
    (2024, False, {}, True),
    (2025, False, {"receptions": 1.0}, False),
    (2023, False, {}, False),
    (2025, True, {}, False),
    (2025, True, {"receptions": 0.0}, False),
    (2024, True, {"receptions": 1.0}, False),
    (2025, True, {"receptions": 1.0}, True),
])
def test_season_guard(season: int, holdout: bool, picks: dict, allowed: bool) -> None:
    assert (season_error(season, holdout, picks) is None) == allowed


@pytest.fixture(autouse=True)
def _no_database_run(monkeypatch: pytest.MonkeyPatch) -> None:
    # A CLI test must never score a season: a guard that wrongly lets a run through fails here instead.
    def refuse(*args: object) -> None:
        raise AssertionError("a CLI test reached a scored or counted run")
    monkeypatch.setattr(nfl_usage_shift, "_main", refuse)
    monkeypatch.setattr(nfl_usage_shift, "_count", refuse)


def test_cli_refuses_the_holdout_without_a_committed_pick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nfl_usage_shift, "USAGE_SHIFT_TRANSFER_BY_MARKET", {})
    monkeypatch.setattr(sys, "argv", ["nfl_usage_shift", "--season", "2025", "--holdout"])

    with pytest.raises(SystemExit):
        nfl_usage_shift.main()


def test_count_report_prints_counts_and_no_projection() -> None:
    cases = [_case(1, "receptions", 41.5, True), _case(2, "receptions", 41.5), _case(3, "rushing_yards", 41.5)]

    text = count_report(cases, rows=10, rows_without_moneyline=2)

    assert "without a closing moneyline: 2" in text
    assert next(line for line in text.splitlines() if line.strip().startswith("receptions")).split() == ["receptions", "2", "1"]
    assert "41.5" not in text and "50" not in text.replace("usage_shift_t10", "")


def test_cli_refuses_count_only_with_the_holdout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["nfl_usage_shift", "--count-only", "--season", "2025", "--holdout"])

    with pytest.raises(SystemExit):
        nfl_usage_shift.main()
