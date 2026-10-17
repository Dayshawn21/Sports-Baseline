import datetime as dt

from app.core.nba_slate import NbaResult, Record, adjacent_dates, slate_date, team_records

D = dt.date
DATES = [D(2026, 6, 13), D(2026, 10, 20), D(2026, 10, 21)]


def test_requested_date_is_kept_even_without_games() -> None:
    assert slate_date(D(2026, 10, 10), D(2026, 10, 6), DATES) == D(2026, 10, 10)


def test_today_with_games_is_served() -> None:
    assert slate_date(None, D(2026, 10, 20), DATES) == D(2026, 10, 20)


def test_today_without_games_moves_to_the_next_game_date() -> None:
    assert slate_date(None, D(2026, 10, 6), DATES) == D(2026, 10, 20)


def test_after_the_last_game_serves_the_latest_date() -> None:
    assert slate_date(None, D(2026, 11, 1), DATES) == D(2026, 10, 21)


def test_no_games_at_all_serves_today() -> None:
    assert slate_date(None, D(2026, 10, 6), []) == D(2026, 10, 6)


def test_adjacent_dates_skip_the_date_itself_and_stop_at_the_ends() -> None:
    assert adjacent_dates(D(2026, 10, 20), DATES) == (D(2026, 6, 13), D(2026, 10, 21))
    assert adjacent_dates(D(2026, 10, 10), DATES) == (D(2026, 6, 13), D(2026, 10, 20))
    assert adjacent_dates(D(2026, 6, 13), DATES) == (None, D(2026, 10, 20))
    assert adjacent_dates(D(2026, 10, 21), DATES) == (D(2026, 10, 20), None)


def _result(game_date: dt.date, home_score: int | None = 110, away_score: int | None = 100, *,
            season: int = 2026, game_type: str = "REG", status: str = "completed") -> NbaResult:
    return NbaResult(season, game_type, game_date, status, "DET", "BOS", home_score, away_score)


def test_records_count_only_completed_regular_season_games_before_the_date() -> None:
    results = [
        _result(D(2026, 10, 20)),
        _result(D(2026, 10, 22), 90, 101),
        _result(D(2026, 10, 23)),
        _result(D(2026, 10, 21), game_type="PIN"),
        _result(D(2026, 10, 21), game_type="PST"),
        _result(D(2026, 4, 1), season=2025),
        _result(D(2026, 10, 21), None, None, status="scheduled"),
    ]
    assert team_records(results, 2026, D(2026, 10, 23)) == {"DET": Record(1, 1), "BOS": Record(1, 1)}


def test_no_games_before_the_date_gives_no_records() -> None:
    assert team_records([_result(D(2026, 10, 20))], 2026, D(2026, 10, 20)) == {}
