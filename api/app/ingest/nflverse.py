"""Read-only NFLverse historical schedule and weekly-player-stat adapter.

NFLverse publishes data through GitHub release assets. This module only fetches
and normalizes those public CSVs; persistence belongs in an NFL repository and a
later ingest command. That separation makes the source easy to test and replace.
"""
from __future__ import annotations

import csv
import argparse
import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from io import StringIO
from math import isfinite
from zoneinfo import ZoneInfo

import httpx
from tenacity import AsyncRetrying, RetryCallState, retry_if_exception_type, retry_if_result, stop_after_attempt, wait_exponential

from app.core.nfl_fantasy import NflFantasyComponents, prizepicks_fantasy_points

logger = logging.getLogger(__name__)

NFLVERSE_RELEASE_BASE = "https://github.com/nflverse/nflverse-data/releases/download"
# NFLverse updates an asset by deleting and re-uploading it, so its URL answers
# 404 until the upload finishes; one such 404 skipped every step of the
# 2026-10-06 nfl-ingest run. Waits are 10, 20 and 40 s, about 70 s per asset.
RELEASE_RETRY_ATTEMPTS = 4
RELEASE_RETRY_WAIT = wait_exponential(multiplier=10, max=60)
# Older seasons use the code a franchise had at the time. Mapping to the current
# code keeps one team row, so a relocated team carries one rating history.
FRANCHISE_CODES = {"OAK": "LV", "SD": "LAC", "STL": "LA"}
NFL_SCHEDULE_TIME_ZONE = ZoneInfo("America/New_York")


def franchise_code(code: str) -> str:
    return FRANCHISE_CODES.get(code, code)


class SeasonNotPublished(Exception):
    """NFLverse has no release asset for the requested season."""

    def __init__(self, season: int, asset: str = "weekly player stats") -> None:
        super().__init__(f"NFLverse has not published {asset} for season {season}")
        self.season = season


def is_retryable_status(status_code: int) -> bool:
    return status_code == 404 or status_code >= 500


def _log_retry(url: str) -> Callable[[RetryCallState], None]:
    def log(state: RetryCallState) -> None:
        outcome = state.outcome
        if outcome is None:
            return
        reason = repr(outcome.exception()) if outcome.failed else f"HTTP {outcome.result().status_code}"
        logger.warning(
            "NFLverse download %s failed (%s), retry %d of %d",
            url, reason, state.attempt_number, RELEASE_RETRY_ATTEMPTS - 1,
        )

    return log


def _last_outcome(state: RetryCallState) -> httpx.Response:
    assert state.outcome is not None
    return state.outcome.result()


async def retry_release_download(url: str, download: Callable[[], Awaitable[httpx.Response]]) -> httpx.Response:
    """Run one release download, retrying a 404, a 5xx or a transport error.

    Returns the last response rather than raising on its status, so a caller
    still turns a final 404 into SeasonNotPublished.
    """
    retrying = AsyncRetrying(
        stop=stop_after_attempt(RELEASE_RETRY_ATTEMPTS),
        wait=RELEASE_RETRY_WAIT,
        retry=retry_if_exception_type(httpx.TransportError) | retry_if_result(lambda response: is_retryable_status(response.status_code)),
        before_sleep=_log_retry(url),
        retry_error_callback=_last_outcome,
    )
    return await retrying(download)


async def get_release_asset(client: httpx.AsyncClient, url: str, timeout: float) -> httpx.Response:
    return await retry_release_download(url, lambda: client.get(url, timeout=timeout))


@dataclass(frozen=True)
class NflverseGame:
    game_id: str
    season: int
    week: int
    game_type: str
    game_date: date
    start_utc: datetime | None
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    spread_line: float | None
    total_line: float | None
    home_moneyline: int | None
    away_moneyline: int | None
    roof: str | None
    home_rest: int | None
    away_rest: int | None
    # Recorded after the game (degrees F, mph), not forecast; NULL indoors.
    temp: int | None = None
    wind: int | None = None


@dataclass(frozen=True)
class NflversePlayerWeek:
    player_id: str
    player_name: str
    position: str | None
    team: str
    opponent: str | None
    game_id: str
    season: int
    week: int
    passing_yards: int
    passing_attempts: int
    passing_completions: int
    rushing_yards: int
    rushing_attempts: int
    receiving_yards: int
    receptions: int
    targets: int | None
    target_share: float | None
    air_yards_share: float | None
    wopr: float | None
    touchdowns: int
    fantasy_points: float | None
    passing_tds: int | None = None
    interceptions: int | None = None
    fumbles_lost: int | None = None
    two_point_conversions: int | None = None
    return_tds: int | None = None
    fumble_recovery_tds: int | None = None
    prizepicks_fantasy_points: float | None = None
    fg_made: int | None = None
    pat_made: int | None = None


def current_nfl_season(today: date) -> int:
    """The NFL season in progress or most recently finished on `today`.

    A season is named for the year it kicks off in September, and its playoffs
    run into February, so January and February belong to the previous year.
    """
    return today.year if today.month >= 3 else today.year - 1


def schedule_url(season: int) -> str:
    return f"{NFLVERSE_RELEASE_BASE}/schedules/games.csv?season={season}"


def player_stats_url(season: int) -> str:
    # The older player_stats aggregate is frozen at 2023-2024 and carries only
    # fantasy-relevant skill players, which is why kickers were unmatchable. The
    # per-season asset covers 2022 onward and every position.
    return f"{NFLVERSE_RELEASE_BASE}/stats_player/stats_player_week_{season}.csv"


def _as_int(value: str | None) -> int:
    try:
        return int(float(value or "0"))
    except ValueError:
        return 0


def _as_optional_int(value: str | None) -> int | None:
    parsed = _as_optional_float(value)
    return int(parsed) if parsed is not None else None


def _as_optional_float(value: str | None) -> float | None:
    try:
        parsed = float(value) if value not in (None, "") else None
    except ValueError:
        return None
    # NaN is not NULL in SQL, so it would pass the usage-evidence filter and
    # poison every average it joins.
    return parsed if parsed is not None and isfinite(parsed) else None


def _scoring_touchdowns(row: dict[str, str]) -> int:
    """Touchdowns scored by the player, for anytime-touchdown baselines."""
    return sum(
        _as_int(row.get(column))
        for column in ("rushing_tds", "receiving_tds")
    )


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _schedule_start(row: dict[str, str], game_date: date) -> datetime | None:
    explicit_start = _parse_datetime(row.get("start_time"))
    if explicit_start is not None:
        if explicit_start.tzinfo is not None:
            return explicit_start.astimezone(timezone.utc)
        return explicit_start.replace(tzinfo=NFL_SCHEDULE_TIME_ZONE).astimezone(timezone.utc)
    game_time = row.get("gametime")
    if not game_time:
        return None
    try:
        return datetime.combine(game_date, time.fromisoformat(game_time), NFL_SCHEDULE_TIME_ZONE).astimezone(timezone.utc)
    except ValueError:
        return None


def parse_schedules(csv_text: str, season: int) -> list[NflverseGame]:
    """Normalize regular-season games from an NFLverse schedules CSV."""
    games: list[NflverseGame] = []
    for row in csv.DictReader(StringIO(csv_text)):
        if _as_int(row.get("season")) != season or row.get("game_type") != "REG":
            continue
        game_date_raw = row.get("gameday") or row.get("game_date")
        if not game_date_raw or not row.get("game_id"):
            continue
        try:
            game_date = date.fromisoformat(game_date_raw[:10])
        except ValueError:
            continue
        games.append(
            NflverseGame(
                game_id=row["game_id"], season=season, week=_as_int(row.get("week")),
                game_type="REG", game_date=game_date,
                start_utc=_schedule_start(row, game_date),
                home_team=franchise_code(row.get("home_team") or ""),
                away_team=franchise_code(row.get("away_team") or ""),
                home_score=_as_optional_int(row.get("home_score")),
                away_score=_as_optional_int(row.get("away_score")),
                spread_line=_as_optional_float(row.get("spread_line")),
                total_line=_as_optional_float(row.get("total_line")),
                home_moneyline=_as_optional_int(row.get("home_moneyline")),
                away_moneyline=_as_optional_int(row.get("away_moneyline")),
                roof=row.get("roof") or None,
                home_rest=_as_optional_int(row.get("home_rest")),
                away_rest=_as_optional_int(row.get("away_rest")),
                temp=_as_optional_int(row.get("temp")),
                wind=_as_optional_int(row.get("wind")),
            )
        )
    return games


def parse_player_stats(csv_text: str, season: int) -> list[NflversePlayerWeek]:
    """Normalize regular-season weekly player stats used by the initial models."""
    stats: list[NflversePlayerWeek] = []
    for row in csv.DictReader(StringIO(csv_text)):
        if _as_int(row.get("season")) != season or row.get("season_type") not in ("REG", None, ""):
            continue
        player_id = row.get("player_id") or row.get("gsis_id")
        team = row.get("recent_team") or row.get("team")
        # The per-season asset carries both "P.Mahomes" and "Patrick Mahomes".
        # Store the full name: providers send full names, and the abbreviated
        # form collapses distinct players (three J.Williams already collide).
        player_name = row.get("player_display_name") or row.get("player_name") or ""
        opponent = row.get("opponent_team")
        if not player_id or not team or not opponent:
            continue
        stats.append(
            NflversePlayerWeek(
                player_id=player_id, player_name=player_name,
                position=row.get("position"), team=franchise_code(team), opponent=franchise_code(opponent),
                game_id=row.get("game_id") or "", season=season, week=_as_int(row.get("week")),
                passing_yards=_as_int(row.get("passing_yards")),
                # NFLverse names these "attempts" and "carries", not
                # "passing_attempts"/"rushing_attempts". A wrong key here reads as a
                # legitimate zero rather than failing, so it stays silent.
                passing_attempts=_as_int(row.get("attempts")),
                passing_completions=_as_int(row.get("completions")),
                rushing_yards=_as_int(row.get("rushing_yards")),
                rushing_attempts=_as_int(row.get("carries")),
                receiving_yards=_as_int(row.get("receiving_yards")),
                receptions=_as_int(row.get("receptions")),
                targets=_as_optional_int(row.get("targets")),
                target_share=_as_optional_float(row.get("target_share")),
                air_yards_share=_as_optional_float(row.get("air_yards_share")),
                wopr=_as_optional_float(row.get("wopr")),
                touchdowns=_scoring_touchdowns(row),
                fantasy_points=_as_optional_float(row.get("fantasy_points_ppr")),
                **_fantasy_components(row),
                fg_made=_as_optional_int(row.get("fg_made")),
                pat_made=_as_optional_int(row.get("pat_made")),
            )
        )
    return stats


def _optional_sum(row: dict[str, str], columns: tuple[str, ...]) -> int | None:
    values = [_as_optional_int(row.get(column)) for column in columns]
    return None if None in values else sum(values)


def _fantasy_components(row: dict[str, str]) -> dict[str, int | float | None]:
    """Scoring components beyond the prop stats, and PrizePicks points built from them.

    A blank component stays None rather than zero, and so does the derived total:
    a missing interception count would otherwise overstate a QB's points.
    """
    fields: dict[str, int | None] = {
        "passing_tds": _as_optional_int(row.get("passing_tds")),
        "interceptions": _as_optional_int(row.get("passing_interceptions")),
        "fumbles_lost": _optional_sum(row, ("sack_fumbles_lost", "rushing_fumbles_lost", "receiving_fumbles_lost")),
        "two_point_conversions": _optional_sum(
            row, ("passing_2pt_conversions", "rushing_2pt_conversions", "receiving_2pt_conversions"),
        ),
        "return_tds": _as_optional_int(row.get("special_teams_tds")),
        "fumble_recovery_tds": _as_optional_int(row.get("fumble_recovery_tds")),
    }
    scoring_touchdowns = _optional_sum(row, ("rushing_tds", "receiving_tds"))
    if None in fields.values() or scoring_touchdowns is None:
        return {**fields, "prizepicks_fantasy_points": None}
    components = NflFantasyComponents(
        passing_yards=_as_int(row.get("passing_yards")),
        rushing_yards=_as_int(row.get("rushing_yards")),
        receiving_yards=_as_int(row.get("receiving_yards")),
        receptions=_as_int(row.get("receptions")),
        touchdowns=scoring_touchdowns,
        **fields,
    )
    return {**fields, "prizepicks_fantasy_points": prizepicks_fantasy_points(components)}


class NflverseClient:
    """Small HTTP client used by a future write-side NFL ingest command."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def fetch_season(self, season: int) -> tuple[list[NflverseGame], list[NflversePlayerWeek]]:
        schedule_response, stats_response = await self._fetch_pair(season)
        return (
            parse_schedules(schedule_response.text, season),
            parse_player_stats(stats_response.text, season),
        )

    async def _fetch_pair(self, season: int) -> tuple[httpx.Response, httpx.Response]:
        schedule_response = await get_release_asset(self._client, schedule_url(season), timeout=60)
        stats_response = await get_release_asset(self._client, player_stats_url(season), timeout=60)
        schedule_response.raise_for_status()
        # The schedule asset is one whole-history file that answers 200 for any
        # season, so an unreleased season is only visible as a 404 on the stats
        # asset. Name the season rather than surfacing a bare HTTPStatusError.
        if stats_response.status_code == 404:
            raise SeasonNotPublished(season)
        stats_response.raise_for_status()
        return schedule_response, stats_response

    async def fetch_schedules(self, seasons: range) -> dict[int, list[NflverseGame]]:
        """Games only, for seasons older than the player-stats asset.

        The schedule asset is one whole-history file, so it is fetched once.
        """
        response = await get_release_asset(self._client, schedule_url(seasons.start), timeout=60)
        response.raise_for_status()
        return {season: parse_schedules(response.text, season) for season in seasons}


async def _store_season(db, games: list[NflverseGame], stats: list[NflversePlayerWeek]) -> tuple[int, int]:
    """Persist one season idempotently after both public files parse successfully."""
    from app.repositories import nfl as nfl_repo

    game_ids: dict[str, int] = {}
    game_by_team_week: dict[tuple[int, str, str], int] = {}
    teams: dict[str, int] = {}
    for game in games:
        home_id = teams.get(game.home_team)
        if home_id is None:
            home_id = await nfl_repo.upsert_team(db, game.home_team)
            teams[game.home_team] = home_id
        away_id = teams.get(game.away_team)
        if away_id is None:
            away_id = await nfl_repo.upsert_team(db, game.away_team)
            teams[game.away_team] = away_id
        game_ids[game.game_id] = await nfl_repo.upsert_game(db, game, home_id, away_id)
        game_by_team_week[(game.week, game.home_team, game.away_team)] = game_ids[game.game_id]
        game_by_team_week[(game.week, game.away_team, game.home_team)] = game_ids[game.game_id]

    stored_stats = 0
    for stat in stats:
        game_id = game_ids.get(stat.game_id) or game_by_team_week.get((stat.week, stat.team, stat.opponent or ""))
        if game_id is None:
            continue
        team_id = teams.get(stat.team)
        if team_id is None:
            team_id = await nfl_repo.upsert_team(db, stat.team)
            teams[stat.team] = team_id
        opponent_id = teams.get(stat.opponent) if stat.opponent else None
        if stat.opponent and opponent_id is None:
            opponent_id = await nfl_repo.upsert_team(db, stat.opponent)
            teams[stat.opponent] = opponent_id
        player_id = await nfl_repo.upsert_player(db, stat.player_id, stat.player_name, stat.position, team_id)
        await nfl_repo.upsert_weekly_stat(db, stat, player_id, game_id, team_id, opponent_id)
        stored_stats += 1
    return len(games), stored_stats


async def run(season: int, dry_run: bool = False) -> tuple[int, int]:
    """Fetch then atomically upsert an NFLverse regular-season backfill."""
    from app.db.pool import SessionLocal

    async with httpx.AsyncClient(follow_redirects=True) as client:
        games, stats = await NflverseClient(client).fetch_season(season)
    if dry_run:
        return len(games), len(stats)
    async with SessionLocal() as db:
        try:
            result = await _store_season(db, games, stats)
            await db.commit()
            return result
        except Exception:
            await db.rollback()
            raise


async def run_schedules(seasons: range, dry_run: bool = False) -> dict[int, int]:
    """Fetch then atomically upsert regular-season games for a season range."""
    from app.db.pool import SessionLocal

    async with httpx.AsyncClient(follow_redirects=True) as client:
        games_by_season = await NflverseClient(client).fetch_schedules(seasons)
    counts = {season: len(games) for season, games in games_by_season.items()}
    if dry_run:
        return counts
    async with SessionLocal() as db:
        try:
            for games in games_by_season.values():
                await _store_season(db, games, [])
            await db.commit()
            return counts
        except Exception:
            await db.rollback()
            raise


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Backfill NFLverse schedule and weekly player stats")
    parser.add_argument(
        "--season", type=int, default=None,
        help="season to load; defaults to the season in progress, so a scheduled run needs no year",
    )
    parser.add_argument(
        "--schedule-only", action="store_true",
        help="load games without player stats, for seasons before the 2022 stats asset",
    )
    parser.add_argument("--through-season", type=int, default=None, help="last season of a --schedule-only range")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    season = args.season if args.season is not None else current_nfl_season(date.today())
    if args.through_season is not None and not args.schedule_only:
        parser.error("--through-season requires --schedule-only")
    if args.schedule_only:
        through = args.through_season if args.through_season is not None else season
        counts = await run_schedules(range(season, through + 1), args.dry_run)
        for loaded_season, count in counts.items():
            print(f"NFLverse {'would load' if args.dry_run else 'loaded'} {count} games for season {loaded_season}")
        return
    try:
        games, stats = await run(season, args.dry_run)
    except SeasonNotPublished as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1)
    print(
        f"NFLverse {'would load' if args.dry_run else 'loaded'} {games} games and "
        f"{stats} player-week rows for season {season}"
    )


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
