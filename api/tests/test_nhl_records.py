from datetime import date

from app.core.nhl_records import NhlRecord, NhlResult, team_records

SLATE = date(2026, 11, 9)


def _result(home_score: int | None, away_score: int | None, end_period: str | None = "REG", **overrides: object) -> NhlResult:
    fields: dict[str, object] = {
        "season": 2026, "game_type": "REG", "game_date": date(2026, 11, 1), "status": "completed",
        "end_period": end_period, "home_team": "NYR", "away_team": "BOS",
        "home_score": home_score, "away_score": away_score, **overrides,
    }
    return NhlResult(**fields)  # type: ignore[arg-type]


def test_overtime_and_shootout_losses_are_the_third_number() -> None:
    results = [_result(4, 1), _result(2, 3, "OT"), _result(3, 2, "SO"), _result(1, 5)]
    assert team_records(results, 2026, SLATE) == {"NYR": NhlRecord(2, 1, 1), "BOS": NhlRecord(2, 1, 1)}


def test_a_win_in_any_period_is_a_win() -> None:
    results = [_result(2, 1, "OT"), _result(2, 1, "SO"), _result(2, 1, "REG")]
    assert team_records(results, 2026, SLATE) == {"NYR": NhlRecord(3, 0, 0), "BOS": NhlRecord(0, 1, 2)}


def test_a_completed_game_with_no_end_period_is_a_regulation_loss() -> None:
    assert team_records([_result(1, 4, None)], 2026, SLATE) == {"BOS": NhlRecord(1, 0, 0), "NYR": NhlRecord(0, 1, 0)}


def test_other_seasons_playoffs_unfinished_and_later_games_are_left_out() -> None:
    results = [
        _result(4, 1, season=2025), _result(4, 1, game_type="PST"), _result(None, None, None, status="scheduled"),
        _result(4, 1, status="postponed"), _result(4, 1, game_date=SLATE), _result(4, 1, game_date=date(2026, 11, 12)),
        _result(None, 2), _result(2, 2),
    ]
    assert team_records(results, 2026, SLATE) == {}
