"""NBA preseason games and box scores from ESPN's site API.

hoopR's release files carry no preseason, so this reads ESPN directly, with the
same ids, into the 20b tables under `game_type = 'PRE'` and no week. Preseason
is for seeing early roles only: readers that build baselines, project or grade
never read `PRE` rows.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.nba_season import ESPN_PRESEASON_TYPE, NBA_TEAM_CODES, PRESEASON, current_nba_season, stored_season
from app.ingest.hoopr_nba import IngestSummary, NbaGame, NbaPlayerGame, store_games

ESPN_NBA_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
EASTERN = ZoneInfo("America/New_York")

_COUNT_KEYS = {
    "points": "points",
    "rebounds": "rebounds",
    "offensiveRebounds": "offensive_rebounds",
    "defensiveRebounds": "defensive_rebounds",
    "assists": "assists",
    "steals": "steals",
    "blocks": "blocks",
    "turnovers": "turnovers",
    "fouls": "fouls",
    "plusMinus": "plus_minus",
}
_MADE_ATTEMPTED_KEYS = {
    "fieldGoalsMade-fieldGoalsAttempted": ("field_goals_made", "field_goals_attempted"),
    "threePointFieldGoalsMade-threePointFieldGoalsAttempted": ("three_pointers_made", "three_pointers_attempted"),
    "freeThrowsMade-freeThrowsAttempted": ("free_throws_made", "free_throws_attempted"),
}


def _start_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _count(value: str | None) -> int | None:
    if value is None or value.strip() in ("", "--"):
        return None
    # plusMinus arrives signed ("+5"); int() accepts the sign.
    return int(value)


def _made_attempted(value: str | None) -> tuple[int | None, int | None]:
    if value is None or "-" not in value:
        return None, None
    made, attempted = value.split("-", 1)
    return _count(made), _count(attempted)


def parse_scoreboard(payload: dict) -> list[NbaGame]:
    """Preseason games between NBA teams on one scoreboard date; regular-season events are 20b's."""
    games = []
    for event in payload.get("events") or []:
        season = event.get("season") or {}
        if season.get("type") != ESPN_PRESEASON_TYPE:
            continue
        competitors = {side["homeAway"]: side for side in event["competitions"][0]["competitors"]}
        home, away = competitors["home"], competitors["away"]
        if not {home["team"]["abbreviation"], away["team"]["abbreviation"]} <= NBA_TEAM_CODES:
            continue
        status = event["status"]["type"]
        completed = bool(status.get("completed"))
        start = _start_utc(event["date"])
        games.append(NbaGame(
            game_id=str(event["id"]),
            season=stored_season(int(season["year"])),
            week=None,
            game_type=PRESEASON,
            # ESPN files games by the Eastern date, so a 00:30Z tip belongs to the day before.
            game_date=start.astimezone(EASTERN).date(),
            start_utc=start,
            home_team=home["team"]["abbreviation"],
            home_team_name=home["team"]["displayName"],
            away_team=away["team"]["abbreviation"],
            away_team_name=away["team"]["displayName"],
            home_score=_count(home.get("score")) if completed else None,
            away_score=_count(away.get("score")) if completed else None,
            status="completed" if completed else "scheduled",
        ))
    return games


def parse_summary(payload: dict, game: NbaGame) -> list[NbaPlayerGame]:
    """Player box scores for one game. An athlete with no stats keeps NULL stats, never zeros."""
    rows = []
    for team in (payload.get("boxscore") or {}).get("players") or []:
        code = team["team"]["abbreviation"]
        is_home = code == game.home_team
        opponent = game.away_team if is_home else game.home_team
        for block in team.get("statistics") or []:
            keys = block.get("keys") or []
            for entry in block.get("athletes") or []:
                athlete = entry.get("athlete") or {}
                if not athlete.get("id"):
                    continue
                stats = dict(zip(keys, entry.get("stats") or []))
                values: dict[str, int | None] = {column: _count(stats.get(key)) for key, column in _COUNT_KEYS.items()}
                for key, (made, attempted) in _MADE_ATTEMPTED_KEYS.items():
                    values[made], values[attempted] = _made_attempted(stats.get(key))
                minutes = stats.get("minutes")
                rows.append(NbaPlayerGame(
                    game_id=game.game_id,
                    player_id=str(athlete["id"]),
                    player_name=athlete.get("displayName", ""),
                    position=(athlete.get("position") or {}).get("abbreviation"),
                    team=code,
                    opponent=opponent,
                    season=game.season,
                    is_home=is_home,
                    starter=bool(entry.get("starter")),
                    did_not_play=bool(entry.get("didNotPlay")),
                    dnp_reason=(entry.get("reason") or None) if entry.get("didNotPlay") else None,
                    minutes=float(minutes) if minutes not in (None, "", "--") else None,
                    **values,
                ))
    return rows


def scoreboard_date(day: date) -> str:
    return day.strftime("%Y%m%d")


# ESPN's site API is unofficial; a short pause keeps a backfill polite.
REQUEST_PAUSE_S = 0.5


async def _get_json(client: httpx.AsyncClient, path: str, params: dict[str, str]) -> dict:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=10),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    ):
        with attempt:
            response = await client.get(f"{ESPN_NBA_BASE}/{path}", params=params, timeout=30)
            response.raise_for_status()
            return response.json()
    raise RuntimeError("unreachable")


async def fetch_preseason(client: httpx.AsyncClient, start: date, end: date) -> tuple[list[NbaGame], list[NbaPlayerGame]]:
    """Preseason games dated start..end, with box scores for the completed ones."""
    games: dict[str, NbaGame] = {}
    day = start
    while day <= end:
        for game in parse_scoreboard(await _get_json(client, "scoreboard", {"dates": scoreboard_date(day)})):
            games[game.game_id] = game
        await asyncio.sleep(REQUEST_PAUSE_S)
        day += timedelta(days=1)
    rows: list[NbaPlayerGame] = []
    for game in games.values():
        if game.status != "completed":
            continue
        rows.extend(parse_summary(await _get_json(client, "summary", {"event": game.game_id}), game))
        await asyncio.sleep(REQUEST_PAUSE_S)
    return list(games.values()), rows


async def run(start: date, end: date, dry_run: bool = False) -> IngestSummary:
    from app.db.pool import SessionLocal

    async with httpx.AsyncClient(follow_redirects=True) as client:
        games, rows = await fetch_preseason(client, start, end)
    summary = IngestSummary(season=games[0].season if games else current_nba_season(start))
    if dry_run or not games:
        summary.games, summary.player_games = len(games), len(rows)
        summary.players = len({row.player_id for row in rows})
        return summary
    async with SessionLocal() as db:
        try:
            await store_games(db, games, rows, summary)
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return summary


async def _main() -> None:
    today = date.today()
    parser = argparse.ArgumentParser(description="Load NBA preseason games and box scores from ESPN's site API")
    parser.add_argument("--start", type=date.fromisoformat, default=date(current_nba_season(today), 10, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=today + timedelta(days=14))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.end < args.start:
        parser.error("--end is before --start")
    summary = await run(args.start, args.end, args.dry_run)
    verb = "would load" if args.dry_run else "loaded"
    print(
        f"ESPN NBA preseason {verb} {summary.games} games, {summary.player_games} player-game rows "
        f"and {summary.players} players, {args.start} to {args.end}"
    )


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
