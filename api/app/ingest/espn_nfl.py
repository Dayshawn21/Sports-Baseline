"""Best-effort ESPN completed-game box-score adapter.

ESPN's public endpoints are undocumented. Callers should cache completed event
summaries permanently and treat source availability as non-guaranteed.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date

import httpx

from app.core.nfl_fantasy import ppr_fantasy_points

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"


@dataclass(frozen=True)
class EspnPlayerStat:
    athlete_id: str
    name: str
    position: str | None
    team: str
    passing_yards: int = 0
    passing_attempts: int = 0
    passing_completions: int = 0
    passing_tds: int = 0
    interceptions: int = 0
    rushing_yards: int = 0
    rushing_attempts: int = 0
    rushing_tds: int = 0
    receiving_yards: int = 0
    receptions: int = 0
    receiving_tds: int = 0

    @property
    def touchdowns(self) -> int:
        return self.passing_tds + self.rushing_tds + self.receiving_tds

    @property
    def fantasy_points(self) -> float:
        return ppr_fantasy_points(self.passing_yards, self.passing_tds, self.interceptions, self.rushing_yards, self.rushing_tds, self.receiving_yards, self.receiving_tds, self.receptions)


def _number(value: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def parse_summary_players(summary: dict) -> list[EspnPlayerStat]:
    """Map ESPN box-score passing, rushing, and receiving groups by stat labels."""
    players: dict[str, dict] = {}
    for team in summary.get("boxscore", {}).get("players", []):
        team_code = team.get("team", {}).get("abbreviation", "")
        for group in team.get("statistics", []):
            group_name = group.get("name")
            labels = group.get("names", [])
            for entry in group.get("athletes", []):
                athlete = entry.get("athlete", {})
                athlete_id = str(athlete.get("id", ""))
                if not athlete_id:
                    continue
                record = players.setdefault(athlete_id, {"athlete_id": athlete_id, "name": athlete.get("displayName", ""), "position": (athlete.get("position") or {}).get("abbreviation"), "team": team_code})
                values = dict(zip(labels, entry.get("stats", [])))
                if group_name == "passing":
                    record.update(passing_completions=_number(values.get("C/ATT", "0").split("/")[0]), passing_attempts=_number(values.get("C/ATT", "0").split("/")[-1]), passing_yards=_number(values.get("YDS")), passing_tds=_number(values.get("TD")), interceptions=_number(values.get("INT")))
                elif group_name == "rushing":
                    record.update(rushing_attempts=_number(values.get("CAR")), rushing_yards=_number(values.get("YDS")), rushing_tds=_number(values.get("TD")))
                elif group_name == "receiving":
                    record.update(receptions=_number(values.get("REC")), receiving_yards=_number(values.get("YDS")), receiving_tds=_number(values.get("TD")))
    return [EspnPlayerStat(**record) for record in players.values()]


class EspnNflClient:
    async def completed_event_ids(self, game_date: date) -> list[str]:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/scoreboard", params={"dates": game_date.strftime("%Y%m%d")}, timeout=20)
            response.raise_for_status()
            return [event["id"] for event in response.json().get("events", []) if event.get("status", {}).get("type", {}).get("completed")]

    async def summary(self, event_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/summary", params={"event": event_id}, timeout=20)
            response.raise_for_status()
            return response.json()
