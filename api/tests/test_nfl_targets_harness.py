import asyncio
import sys
from types import ModuleType

import pytest

from app.backtest import nfl_targets_projections as harness
from app.core.nfl_targets_backtest import select_baseline
from app.core.nfl_targets_projection import TargetsObservation, TargetsProjectionInput, TargetsReplayRow

HISTORY = (0.0, 0.0, 0.0, 0.0, 10.0, 10.0, 10.0, 10.0)


def _row(player_id: int, actual: float | None, position: str = "WR") -> TargetsReplayRow:
    observations = tuple(
        TargetsObservation(1000 * player_id + week, 2024, week, None, value)
        for week, value in enumerate(HISTORY, start=1)
    )
    return TargetsReplayRow(
        player_id, 109, 9, position, TargetsProjectionInput(2024, 9, observations, 0.7, True), actual,
    )


def _adopting_rows() -> list[TargetsReplayRow]:
    return [_row(player_id, 7.02, "WR" if player_id % 2 else "TE") for player_id in range(1, 301)]


@pytest.fixture
def no_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "app.db.pool", None)
    monkeypatch.setitem(sys.modules, "app.repositories.nfl_targets", None)


def test_report_shows_metrics_both_decisions_coverage_and_settings() -> None:
    text = harness.report(select_baseline([*_adopting_rows(), _row(999, None)]))

    assert "Rec Targets baseline, 2024 (model nfl-targets-v1)" in text
    assert "2025 holdout reads: 0." in text
    assert "not week-start snapshots" in text
    assert "recent_form = round((0.5 * B + 0.5 * R) * accepted_factor, 2)." in text
    for arm in ("reference", "moneyline", "recent_form"):
        assert f"Arm {arm}:" in text
    assert "receiving_targets / TE" in text and "receiving_targets / WR" in text
    assert "moneyline vs reference" in text and "recent_form vs moneyline" in text
    week_9 = next(line for line in text.splitlines() if line.startswith("9 "))
    assert week_9.split()[:7] == ["9", "301", "1", "0", "0", "0", "300"]
    assert "Selected development arm: recent_form" in text
    assert "SELECTED_MONEYLINE_SCALING = True" in text
    assert "SELECTED_RECENT_FORM = True" in text


def test_report_on_empty_data_claims_no_selection() -> None:
    text = harness.report(select_baseline([]))

    assert "No eligible cases." in text
    assert "-- no paired cases --  insufficient" in text
    assert "NO SELECTION" in text
    assert "Selected development arm" not in text


def test_help_needs_no_database(no_database: None, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit:
        harness.parse_args(["--help"])

    assert exit.value.code == 0
    assert "2024 only" in capsys.readouterr().out


def test_default_season_is_2024() -> None:
    assert harness.parse_args([]).season == 2024


@pytest.mark.parametrize("season", ["2025", "2023"])
def test_cli_rejects_other_seasons_before_database_access(no_database: None, season: str) -> None:
    with pytest.raises(SystemExit) as exit:
        harness.main(["--season", season])

    assert exit.value.code == 2


def test_run_entry_rejects_other_seasons_before_importing_the_database(no_database: None) -> None:
    with pytest.raises(ValueError, match="2024 only"):
        asyncio.run(harness.run_replay(2025))


def test_run_replay_loads_every_regular_season_week(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, int]] = []

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    async def get_targets_replay_rows(db: FakeSession, season: int, week: int) -> list[TargetsReplayRow]:
        calls.append((season, week))
        return _adopting_rows() if week == 9 else []

    pool = ModuleType("app.db.pool")
    pool.SessionLocal = FakeSession  # type: ignore[attr-defined]
    repository = ModuleType("app.repositories.nfl_targets")
    repository.get_targets_replay_rows = get_targets_replay_rows  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "app.db.pool", pool)
    monkeypatch.setitem(sys.modules, "app.repositories.nfl_targets", repository)

    result = asyncio.run(harness.run_replay(2024))

    assert calls == [(2024, week) for week in range(1, 19)]
    assert result.selected_arm == "recent_form"
    assert sum(week.scored for week in result.coverage) == 300
