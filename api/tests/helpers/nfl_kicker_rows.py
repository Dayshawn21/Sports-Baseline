"""K fantasy rows shaped like the slate query's, for the 27l3 projection and report tests."""
from datetime import UTC, datetime


def kicker_averages(games: int, ppr: float | None, prizepicks: float | None) -> dict:
    return {
        "games": games, "passing_yards": 0.0, "passing_attempts": 0.0, "passing_completions": 0.0,
        "rushing_yards": 0.0, "rushing_attempts": 0.0, "receiving_yards": 0.0, "receptions": 0.0,
        "touchdowns": 0.0, "fantasy_points": ppr, "prizepicks_fantasy_points": prizepicks,
    }


def kicker_season(games: int, player: float | None, position: float = 8.5) -> dict:
    return {
        "averages": kicker_averages(games, 0.0, player), "position_averages": kicker_averages(games * 32, 0.0, position),
        "usage": None, "position_usage": None,
    }


def kicker_line_row(seasons: dict[int, dict], chosen: int = 2025, position: str = "K", market: str = "fantasy_points") -> dict:
    return {
        "id": 1, "game_id": 2, "player_id": 3, "player_name": "Kicker", "position": position,
        "player_team_id": 4, "home_team_id": 4, "market": market, "segment": "full_game",
        "opponent_team": "BUF", "odds_type": "standard", "line": 8.5, "provider": "prizepicks",
        "fetched_at": datetime(2025, 10, 5, 12, tzinfo=UTC),
        "baseline_season": chosen, "baseline_reason": "current_season",
        "averages": seasons[chosen]["averages"], "position_averages": seasons[chosen]["position_averages"],
        "opponent_averages": None, "league_position_averages": None,
        "baseline_seasons": seasons,
    }
