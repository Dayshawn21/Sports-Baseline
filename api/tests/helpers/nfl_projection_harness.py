"""Shared fixtures and builders, first written for `test_nfl_projection_harness.py`."""
from datetime import UTC, datetime


def _averages(games: int, receiving_yards: float) -> dict:
    return {
        "games": games, "passing_yards": 0.0, "passing_attempts": 0.0, "passing_completions": 0.0,
        "rushing_yards": 0.0, "rushing_attempts": 0.0, "receiving_yards": receiving_yards,
        "receptions": 0.0, "touchdowns": 0.0, "fantasy_points": None,
    }


def _replay_row(**overrides: object) -> dict:
    return {
        "id": 1, "game_id": 2, "player_id": 3, "player_name": "Receiver", "position": "WR",
        "player_team_id": 4, "home_team_id": 4, "market": "receiving_yards", "segment": "full_game",
        "opponent_team": "BUF", "opponent_team_id": 5,
        "odds_type": "standard", "line": 0.0, "provider": "replay", "fetched_at": datetime(2025, 11, 9, tzinfo=UTC),
        "baseline_season": 2025, "baseline_reason": "current_season",
        "averages": _averages(8, 60.0), "position_averages": _averages(200, 40.0), "baseline_seasons": {},
        # Per player row: 51 "games" from about 17 real ones, 5% above the league.
        "opponent_averages": _averages(51, 42.0), "league_position_averages": _averages(3000, 40.0),
        # Per team-game: 17 real games, 8% above the league.
        "team_game_opponent_averages": _averages(17, 162.0), "team_game_league_averages": _averages(540, 150.0),
    } | overrides
