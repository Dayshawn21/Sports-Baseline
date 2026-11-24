"""Shared fixtures and builders, first written for `test_nfl_targets_service.py`."""
from __future__ import annotations

from datetime import UTC, date, datetime


from app.core.nfl_availability import NflAvailability
from app.core.nfl_targets_projection import TargetsObservation, TargetsProjectionInput
from app.repositories.nfl_targets import TargetsHistoryGame, TargetsServingLine


FETCHED = datetime(2026, 10, 24, 15, tzinfo=UTC)
NOW = datetime(2026, 10, 24, 16, tzinfo=UTC)
KICKOFF = datetime(2026, 10, 25, 17, tzinfo=UTC)


def _game(game_id: int, value: float | None, *, season: int = 2026, week: int | None = None, game_date: date | None = None) -> TargetsHistoryGame:
    return TargetsHistoryGame(
        TargetsObservation(game_id, season, week if week is not None else game_id, None, value, game_date),
        opponent_team_id=3, opponent_team="BUF",
    )


DEFAULT_HISTORY = tuple(_game(index, value) for index, value in enumerate([1, 2, 4, 6], start=1))


def _source(history: tuple[TargetsHistoryGame, ...] = DEFAULT_HISTORY) -> TargetsServingLine:
    return TargetsServingLine(
        line_id=70, game_id=50, player_id=7, player_name="Receiver", position="WR", player_team_id=2,
        opponent_team_id=3, opponent_team="BUF", start_utc=KICKOFF,
        market="receiving_targets", segment="full_game", odds_type="standard", line=4.5,
        provider="prizepicks", fetched_at=FETCHED,
        input=TargetsProjectionInput(2026, 7, tuple(game.observation for game in history)), history=history,
        availability=NflAvailability(), practice_status=None, injury=None,
    )
