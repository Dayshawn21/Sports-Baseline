"""API-Sports NFL current-stat source.

The active NFL provider follows the documented league -> season -> game ->
player-statistics flow. Only FT and AOT games are eligible for ingest; their
player box scores are immutable and must be fetched once then persisted.
"""
from __future__ import annotations

import httpx

from app.config import settings

BASE_URL = "https://v1.american-football.api-sports.io"
NFL_LEAGUE_ID = 1
FINAL_STATUSES = frozenset({"FT", "AOT"})


class ApiSportsNflClient:
    def __init__(self) -> None:
        self._headers = {"x-apisports-key": settings.api_sports_nfl_key}

    async def current_season(self) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/leagues", params={"current": "true"}, headers=self._headers, timeout=20)
            response.raise_for_status()
            for entry in response.json().get("response", []):
                if entry.get("league", {}).get("id") == NFL_LEAGUE_ID:
                    return next(season for season in entry.get("seasons", []) if season.get("current"))
        raise RuntimeError("API-Sports did not report a current NFL season")

    async def games(self, season: int) -> list[dict]:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/games", params={"league": NFL_LEAGUE_ID, "season": season}, headers=self._headers, timeout=30)
            response.raise_for_status()
            return response.json().get("response", [])


async def completed_games_for_current_season() -> tuple[int, list[dict]]:
    """Return only final games when coverage advertises player game statistics."""
    client = ApiSportsNflClient()
    season = await client.current_season()
    coverage = season.get("coverage", {}).get("games", {}).get("statisitcs", {}).get("players")
    if not coverage:
        return int(season["year"]), []
    games = await client.games(int(season["year"]))
    return int(season["year"]), [game for game in games if game.get("game", {}).get("status", {}).get("short") in FINAL_STATUSES]

    async def completed_game_players(self, game_id: int) -> list[dict]:
        """Fetch one immutable box score only after the game is final."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/games/statistics/players", params={"id": game_id}, headers=self._headers, timeout=30)
            response.raise_for_status()
            return response.json().get("response", [])
