from datetime import date

import pytest

from app.core.nhl_season import current_nhl_season, end_period, game_status, game_type, season_id


@pytest.mark.parametrize(
    ("today", "season"),
    [
        (date(2026, 10, 23), 2026),
        (date(2027, 4, 1), 2026),
        (date(2026, 7, 15), 2025),
        (date(2026, 7, 31), 2025),
        (date(2026, 8, 1), 2026),
        (date(2026, 9, 29), 2026),
    ],
)
def test_current_season_changes_in_august(today: date, season: int) -> None:
    assert current_nhl_season(today) == season


@pytest.mark.parametrize(("season", "expected"), [(2023, "20232024"), (2026, "20262027")])
def test_season_id_combines_start_and_end_year(season: int, expected: str) -> None:
    assert season_id(season) == expected


@pytest.mark.parametrize(("value", "expected"), [(2, "REG"), (3, "PST"), (1, None), (4, None), (99, None)])
def test_only_regular_and_playoff_game_types_are_stored(value: int, expected: str | None) -> None:
    assert game_type(value) == expected


@pytest.mark.parametrize(
    ("state", "schedule_state", "expected"),
    [
        ("OFF", "OK", "completed"),
        ("FINAL", "OK", "completed"),
        ("FUT", "OK", "scheduled"),
        ("PRE", "OK", "scheduled"),
        ("LIVE", "OK", "scheduled"),
        ("CRIT", "OK", "scheduled"),
        ("FUT", "PPD", "postponed"),
        ("OFF", "PPD", "postponed"),
        ("FINAL", "CNCL", "canceled"),
        ("PPD", "OK", "postponed"),
        ("CNCL", "OK", "canceled"),
        ("OFF", "UNKNOWN", "scheduled"),
        ("UNKNOWN", "OK", "scheduled"),
    ],
)
def test_schedule_state_prevents_false_completion(state: str, schedule_state: str, expected: str) -> None:
    assert game_status(state, schedule_state) == expected


@pytest.mark.parametrize("period", ["REG", "OT", "SO"])
def test_completed_game_retains_valid_end_period(period: str) -> None:
    assert end_period("completed", period) == period


@pytest.mark.parametrize("status", ["scheduled", "postponed", "canceled"])
@pytest.mark.parametrize("period", ["REG", "OT", "SO"])
def test_unfinished_game_never_has_end_period(status: str, period: str) -> None:
    assert end_period(status, period) is None


@pytest.mark.parametrize("period", [None, "", "XX"])
def test_completed_game_with_unknown_period_keeps_it_unavailable(period: str | None) -> None:
    assert end_period("completed", period) is None
