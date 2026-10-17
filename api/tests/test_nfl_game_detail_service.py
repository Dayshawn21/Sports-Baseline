import asyncio
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, patch

from app.services.nfl.game_detail import build_game_detail, game_detail

GAME = {"game_id": 40, "season": 2026, "week": 3, "game_date": date(2026, 9, 27),
        "start_utc": datetime(2026, 9, 27, 17, tzinfo=UTC), "away_team": "TEN", "home_team": "NYG", "status": "scheduled"}


def _row(market: str, day: int, line: float) -> dict:
    return {"market": market, "book": "draftkings", "line": line, "fetched_at": datetime(2026, 9, day, 18, tzinfo=UTC)}


def test_detail_carries_the_game_and_collapsed_steps_per_market() -> None:
    rows = [_row("spread", 18, -5.5), _row("spread", 19, -5.5), _row("spread", 22, -3.0), _row("total", 18, 43.5)]

    detail = game_detail(GAME, rows)

    assert (detail.game_id, detail.away_team, detail.home_team, detail.week) == (40, "TEN", "NYG", 3)
    assert [(item.market, [step.line for step in item.steps]) for item in detail.line_history] == [
        ("spread", [-5.5, -3.0]), ("total", [43.5]),
    ]


def test_a_game_without_stored_odds_has_an_empty_history() -> None:
    assert game_detail(GAME, []).line_history == []


def test_the_response_serializes_in_camel_case() -> None:
    body = game_detail(GAME, [_row("total", 18, 43.5)]).model_dump(by_alias=True)
    assert body["lineHistory"][0]["steps"][0]["fetchedAt"] == datetime(2026, 9, 18, 18, tzinfo=UTC)
    assert body["homeTeam"] == "NYG"


def test_an_unknown_game_is_none_and_skips_the_history_query() -> None:
    with patch("app.services.nfl.game_detail.nfl_repo") as repo:
        repo.get_game = AsyncMock(return_value=None)
        repo.get_game_line_history = AsyncMock()

        assert asyncio.run(build_game_detail(AsyncMock(), 999999)) is None
        repo.get_game_line_history.assert_not_called()
