from datetime import date

import pytest

from app.core.nba_season import (
    NBA_TEAM_CODES,
    current_nba_season,
    file_season,
    game_type,
    nba_week,
    opening_night,
    stored_season,
)

OPENING_2026 = date(2026, 10, 20)


def test_stored_season_is_the_start_year():
    assert stored_season(2026) == 2025
    assert file_season(stored_season(2027)) == 2027


@pytest.mark.parametrize(
    ("today", "season"),
    [
        (date(2026, 10, 5), 2026),
        (date(2027, 3, 1), 2026),
        (date(2026, 6, 13), 2025),
        (date(2026, 7, 15), 2025),
        (date(2026, 8, 1), 2026),
    ],
)
def test_current_nba_season(today, season):
    assert current_nba_season(today) == season


def test_opening_night_is_the_earliest_regular_season_date():
    assert opening_night([date(2026, 11, 2), OPENING_2026, date(2027, 4, 11)]) == OPENING_2026


@pytest.mark.parametrize(
    ("game_date", "week"),
    [
        (date(2026, 10, 19), 1),
        (OPENING_2026, 1),
        (date(2026, 10, 25), 1),
        (date(2026, 10, 26), 2),
        (date(2026, 11, 1), 2),
        (date(2026, 11, 2), 3),
    ],
)
def test_week_runs_monday_to_sunday_from_opening_week(game_date, week):
    assert nba_week(game_date, OPENING_2026) == week


def test_week_rejects_a_date_before_opening_week():
    with pytest.raises(ValueError):
        nba_week(date(2026, 10, 18), OPENING_2026)


@pytest.mark.parametrize(("espn_type", "expected"), [(2, "REG"), (5, "PIN"), (3, "PST"), (1, None), (4, None)])
def test_game_type_maps_espn_season_types(espn_type, expected):
    assert game_type(espn_type) == expected


def test_nba_team_codes_are_the_thirty_franchises():
    assert len(NBA_TEAM_CODES) == 30
    assert {"UTAH", "GS", "NY", "SA"} <= NBA_TEAM_CODES
