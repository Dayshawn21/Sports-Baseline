from datetime import date

import pytest

from app.core.regular_season_week import opening_night, regular_season_week


def test_opening_night_uses_earliest_date_from_unsorted_iterable() -> None:
    dates = (date.fromisoformat(value) for value in ("2025-04-01", "2024-10-04", "2024-10-08"))
    assert opening_night(dates) == date(2024, 10, 4)


def test_opening_night_rejects_empty_schedule() -> None:
    with pytest.raises(ValueError):
        opening_night([])


@pytest.mark.parametrize(
    ("game_date", "week"),
    [
        (date(2024, 9, 30), 1),
        (date(2024, 10, 4), 1),
        (date(2024, 10, 6), 1),
        (date(2024, 10, 7), 2),
        (date(2024, 10, 13), 2),
        (date(2024, 10, 14), 3),
        (date(2025, 2, 10), 20),
        (date(2025, 2, 16), 20),
        (date(2025, 2, 17), 21),
    ],
)
def test_prague_opening_and_break_weeks_keep_calendar_number(game_date: date, week: int) -> None:
    assert regular_season_week(game_date, date(2024, 10, 4)) == week


def test_week_rejects_date_before_opening_week() -> None:
    with pytest.raises(ValueError, match="before the week of opening night"):
        regular_season_week(date(2024, 9, 29), date(2024, 10, 4))


@pytest.mark.parametrize(
    ("game_date", "week"),
    [(date(2026, 9, 28), 1), (date(2026, 10, 4), 1), (date(2026, 10, 5), 2)],
)
def test_live_nhl_season_opening_week(game_date: date, week: int) -> None:
    assert regular_season_week(game_date, date(2026, 9, 29)) == week
