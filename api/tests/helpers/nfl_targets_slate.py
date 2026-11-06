"""Shared fixtures and builders, first written for `test_nfl_targets_slate.py`."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.repositories.nfl_targets import TargetsServingLine, TargetsUnmatchedLine
from app.services.nfl import slate
from tests.helpers.nfl_targets_service import KICKOFF


def _game(game_id: int = 50) -> dict[str, object]:
    return {"game_id": game_id, "game_date": KICKOFF.date(), "start_utc": KICKOFF,
            "away_team": "BUF", "home_team": "MIA", "status": "scheduled"}


def _inputs(
    monkeypatch: pytest.MonkeyPatch, games: list[dict[str, object]], v4: list[dict[str, object]],
    targets: list[TargetsServingLine], unmatched: list[TargetsUnmatchedLine] | None = None,
) -> None:
    reads = {
        "get_slate_games": games, "get_slate_lines": v4, "get_slate_player_history": {},
        "get_slate_opponent_position_history": {}, "get_team_game_position_totals": {},
        "get_slate_market_probabilities": {}, "get_slate_matchup_context": {}, "get_slate_weather": {},
        "get_unmatched_slate_lines": [], "get_slate_prop_odds": {}, "get_slate_team_elo": {}, "get_elo_games": [],
        "get_current_week": (2026, 7),
    }
    for name, value in reads.items():
        monkeypatch.setattr(slate.nfl_repo, name, AsyncMock(return_value=value))
    monkeypatch.setattr(slate.targets_repo, "get_targets_serving_lines", AsyncMock(return_value=targets))
    monkeypatch.setattr(slate.targets_repo, "get_unmatched_targets_lines", AsyncMock(return_value=unmatched or []))
    monkeypatch.setattr(slate.volume_repo, "get_volume_serving_lines", AsyncMock(return_value=[]))
