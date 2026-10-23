"""Normalize NHL web schedules and stats REST per-game reports."""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, NotRequired, TypeVar, TypedDict, cast
from zoneinfo import ZoneInfo

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.nhl_season import current_nhl_season, end_period, game_status, game_type, season_id
from app.core.regular_season_week import opening_night, regular_season_week

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

EASTERN = ZoneInfo("America/New_York")
WEB_BASE = "https://api-web.nhle.com/v1"
STATS_BASE = "https://api.nhle.com/stats/rest/en"
REPORTS = ("skater/summary", "skater/realtime", "skater/faceoffwins", "goalie/summary")
StatRow = dict[str, str | int | float | None]


class _Team(TypedDict):
    abbrev: str
    placeName: dict[str, str]
    commonName: dict[str, str]
    score: NotRequired[int]


class _ScheduleGame(TypedDict):
    id: int
    gameType: int
    startTimeUTC: str
    gameState: str
    gameScheduleState: str
    homeTeam: _Team
    awayTeam: _Team
    gameOutcome: NotRequired[dict[str, str]]


class _ScheduleDay(TypedDict):
    games: list[_ScheduleGame]


class ScheduleWeek(TypedDict):
    gameWeek: list[_ScheduleDay]
    regularSeasonStartDate: NotRequired[str]
    playoffEndDate: NotRequired[str]
    nextStartDate: NotRequired[str]


class StatsReport(TypedDict):
    data: list[StatRow]
    total: int


@dataclass(frozen=True)
class NhlGame:
    game_id: str
    season: int
    week: int | None
    game_type: str
    game_date: date
    start_utc: datetime
    home_team: str
    home_team_name: str
    away_team: str
    away_team_name: str
    home_score: int | None
    away_score: int | None
    status: str
    end_period: str | None


@dataclass(frozen=True)
class NhlSkaterGame:
    game_id: str
    player_id: str
    player_name: str
    position: str | None
    team: str
    opponent: str
    season: int
    is_home: bool
    time_on_ice_seconds: int | None
    goals: int | None
    assists: int | None
    points: int | None
    shots: int | None
    power_play_goals: int | None
    power_play_points: int | None
    shorthanded_points: int | None
    plus_minus: int | None
    hits: int | None
    blocked_shots: int | None
    faceoffs_won: int | None
    faceoffs_lost: int | None
    penalty_minutes: int | None
    giveaways: int | None
    takeaways: int | None
    ot_goals: int | None


@dataclass(frozen=True)
class NhlGoalieGame:
    game_id: str
    player_id: str
    player_name: str
    position: str
    team: str
    opponent: str
    season: int
    is_home: bool
    time_on_ice_seconds: int | None
    started: bool
    decision: str | None
    saves: int | None
    shots_against: int | None
    goals_against: int | None


def _int(value: str | int | float | None) -> int | None:
    return None if value is None or value == "" else int(float(value))


def _team_name(team: _Team) -> str:
    return f"{team['placeName']['default']} {team['commonName']['default']}"


def parse_schedule_week(payload: ScheduleWeek) -> tuple[list[NhlGame], Counter[str]]:
    """Parse one week; season-wide opening night and week numbers are assigned later."""
    games: list[NhlGame] = []
    skipped: Counter[str] = Counter()
    for day in payload["gameWeek"]:
        for row in day["games"]:
            kind = game_type(row["gameType"])
            if kind is None:
                skipped[f"game_type_{row['gameType']}"] += 1
                continue
            if not row.get("id"):
                skipped["missing_game_id"] += 1
                continue
            start = datetime.fromisoformat(row["startTimeUTC"].replace("Z", "+00:00"))
            if start.tzinfo is None:
                raise ValueError(f"NHL game {row['id']} has a start time without a UTC offset")
            start = start.astimezone(timezone.utc)
            status = game_status(row["gameState"], row["gameScheduleState"])
            home, away = row["homeTeam"], row["awayTeam"]
            games.append(NhlGame(
                game_id=str(row["id"]), season=int(str(row["id"])[:4]), week=None,
                game_type=kind, game_date=start.astimezone(EASTERN).date(), start_utc=start,
                home_team=home["abbrev"], home_team_name=_team_name(home),
                away_team=away["abbrev"], away_team_name=_team_name(away),
                home_score=home.get("score") if status == "completed" else None,
                away_score=away.get("score") if status == "completed" else None,
                status=status, end_period=end_period(status, row.get("gameOutcome", {}).get("lastPeriodType")),
            ))
    return games, skipped


def _keyed_rows(report: StatsReport, name: str, skipped: Counter[str]) -> dict[tuple[str, str], StatRow]:
    keyed = {}
    for row in report["data"]:
        if not row.get("playerId"):
            skipped[f"{name}_missing_player_id"] += 1
        elif not row.get("gameId"):
            skipped[f"{name}_missing_game_id"] += 1
        else:
            keyed[str(row["playerId"]), str(row["gameId"])] = row
    return keyed


def parse_skater_reports(
    summary: StatsReport, realtime: StatsReport, faceoffwins: StatsReport,
) -> tuple[list[NhlSkaterGame], Counter[str]]:
    """Left-join supplementary stats onto summary by player and game, preserving NULLs."""
    skipped: Counter[str] = Counter()
    summaries = _keyed_rows(summary, "summary", skipped)
    realtime_rows = _keyed_rows(realtime, "realtime", skipped)
    faceoff_rows = _keyed_rows(faceoffwins, "faceoffwins", skipped)
    skaters = []
    for (player_id, game_id), row in summaries.items():
        if row.get("homeRoad") not in ("H", "R"):
            skipped["summary_invalid_home_road"] += 1
            continue
        live = realtime_rows.get((player_id, game_id), {})
        faceoffs = faceoff_rows.get((player_id, game_id), {})
        skaters.append(NhlSkaterGame(
            game_id=game_id, player_id=player_id, player_name=str(row["skaterFullName"]),
            position=str(row["positionCode"]) if row.get("positionCode") else None,
            team=str(row["teamAbbrev"]), opponent=str(row["opponentTeamAbbrev"]),
            season=int(game_id[:4]), is_home=row["homeRoad"] == "H",
            time_on_ice_seconds=_int(row.get("timeOnIcePerGame")),
            goals=_int(row.get("goals")), assists=_int(row.get("assists")),
            points=_int(row.get("points")), shots=_int(row.get("shots")),
            power_play_goals=_int(row.get("ppGoals")), power_play_points=_int(row.get("ppPoints")),
            shorthanded_points=_int(row.get("shPoints")), plus_minus=_int(row.get("plusMinus")),
            hits=_int(live.get("hits")), blocked_shots=_int(live.get("blockedShots")),
            faceoffs_won=_int(faceoffs.get("totalFaceoffWins")), faceoffs_lost=_int(faceoffs.get("totalFaceoffLosses")),
            penalty_minutes=_int(row.get("penaltyMinutes")), giveaways=_int(live.get("giveaways")),
            takeaways=_int(live.get("takeaways")), ot_goals=_int(row.get("otGoals")),
        ))
    return skaters, skipped


def _goalie_decision(row: StatRow) -> str | None:
    for key, decision in (("wins", "W"), ("losses", "L"), ("otLosses", "O")):
        if (_int(row.get(key)) or 0) > 0:
            return decision
    return None


def parse_goalie_summary(summary: StatsReport) -> tuple[list[NhlGoalieGame], Counter[str]]:
    skipped: Counter[str] = Counter()
    goalies = []
    for (player_id, game_id), row in _keyed_rows(summary, "goalie", skipped).items():
        if row.get("homeRoad") not in ("H", "R"):
            skipped["goalie_invalid_home_road"] += 1
            continue
        goalies.append(NhlGoalieGame(
            game_id=game_id, player_id=player_id, player_name=str(row["goalieFullName"]), position="G",
            team=str(row["teamAbbrev"]), opponent=str(row["opponentTeamAbbrev"]),
            season=int(game_id[:4]), is_home=row["homeRoad"] == "H",
            time_on_ice_seconds=_int(row.get("timeOnIce")), started=row.get("gamesStarted") == 1,
            decision=_goalie_decision(row), saves=_int(row.get("saves")),
            shots_against=_int(row.get("shotsAgainst")), goals_against=_int(row.get("goalsAgainst")),
        ))
    return goalies, skipped


@dataclass
class IngestSummary:
    season: int
    games: int
    skater_games: int
    goalie_games: int
    players: int
    teams: int
    skipped: Counter[str] = field(default_factory=Counter)


def _retryable(exc: BaseException) -> bool:
    return isinstance(exc, httpx.TransportError) or (
        isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500
    )


async def _get_json(
    client: httpx.AsyncClient, url: str, params: dict[str, str | int] | None = None,
) -> dict[str, object]:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10),
        retry=retry_if_exception(_retryable), reraise=True,
    ):
        with attempt:
            response = await client.get(url, params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError(f"NHL response is not an object: {url}")
            return payload
    raise RuntimeError("unreachable")


async def fetch_schedule(client: httpx.AsyncClient, season: int) -> tuple[list[NhlGame], Counter[str], date, date]:
    metadata = await _get_json(client, f"{WEB_BASE}/schedule/{season}-10-15")
    first = date.fromisoformat(str(metadata["regularSeasonStartDate"]))
    last = date.fromisoformat(str(metadata["playoffEndDate"]))
    if first > last or first.year != season:
        raise ValueError(f"NHL schedule returned invalid bounds for season {season}")
    current = first
    by_id: dict[str, NhlGame] = {}
    skipped: Counter[str] = Counter()
    while current <= last:
        payload = cast(ScheduleWeek, await _get_json(client, f"{WEB_BASE}/schedule/{current.isoformat()}"))
        games, counts = parse_schedule_week(payload)
        skipped.update(counts)
        for game in games:
            if game.season == season and first <= game.game_date <= last:
                by_id[game.game_id] = game
            else:
                skipped["outside_season"] += 1
        next_date = _next_schedule_date(payload, current)
        if next_date is None:
            break
        current = next_date
    games = sorted(by_id.values(), key=lambda game: (game.start_utc, game.game_id))
    opening = opening_night(game.game_date for game in games if game.game_type == "REG")
    return [
        replace(game, week=regular_season_week(game.game_date, opening) if game.game_type == "REG" else None)
        for game in games
    ], skipped, first, last


def _next_schedule_date(payload: ScheduleWeek, current: date) -> date | None:
    # The final published week omits this field, including before playoffs exist.
    value = payload.get("nextStartDate")
    if not value:
        return None
    next_date = date.fromisoformat(value)
    if next_date <= current:
        raise ValueError(f"NHL weekly schedule did not advance from {current}")
    return next_date


def _month_windows(first: date, last: date) -> Iterable[tuple[date, date]]:
    while first <= last:
        next_month = date(first.year + first.month // 12, first.month % 12 + 1, 1)
        end = min(last, next_month - timedelta(days=1))
        yield first, end
        first = end + timedelta(days=1)


def _validate_report(report: StatsReport, name: str) -> None:
    if report["total"] != len(report["data"]):
        raise ValueError(f"NHL {name} truncated: total {report['total']}, received {len(report['data'])}")


async def fetch_stats(
    client: httpx.AsyncClient, season: int, first: date, last: date,
) -> tuple[list[NhlSkaterGame], list[NhlGoalieGame], Counter[str]]:
    combined: dict[str, StatsReport] = {name: {"data": [], "total": 0} for name in REPORTS}
    for start, end in _month_windows(first, last):
        expression = (
            f'seasonId={season_id(season)} and gameDate>="{start}" and gameDate<="{end}" '
            'and (gameTypeId=2 or gameTypeId=3)'
        )
        for name in REPORTS:
            report = cast(StatsReport, await _get_json(client, f"{STATS_BASE}/{name}", {
                "isAggregate": "false", "isGame": "true", "start": 0, "limit": -1, "cayenneExp": expression,
            }))
            _validate_report(report, name)
            combined[name]["data"].extend(report["data"])
            combined[name]["total"] += report["total"]
    skaters, skipped = parse_skater_reports(*(combined[name] for name in REPORTS[:3]))
    goalies, counts = parse_goalie_summary(combined["goalie/summary"])
    skipped.update(counts)
    return skaters, goalies, skipped


_StatGame = TypeVar("_StatGame", NhlSkaterGame, NhlGoalieGame)


def select_stat_rows(
    rows: Sequence[_StatGame], games: Sequence[NhlGame], first: date, last: date, name: str,
) -> tuple[list[_StatGame], Counter[str]]:
    by_id = {game.game_id: game for game in games}
    selected: list[_StatGame] = []
    skipped: Counter[str] = Counter()
    for row in rows:
        game = by_id.get(row.game_id)
        if game is None:
            skipped[f"{name}_game_not_stored"] += 1
        elif game.status != "completed":
            skipped[f"{name}_game_not_completed"] += 1
        elif not first <= game.game_date <= last:
            skipped[f"{name}_outside_window"] += 1
        elif (row.team, row.opponent) != (
            (game.home_team, game.away_team) if row.is_home else (game.away_team, game.home_team)
        ):
            skipped[f"{name}_team_mismatch"] += 1
        else:
            selected.append(row)
    return selected, skipped


def latest_player_rows(
    rows: Sequence[NhlSkaterGame | NhlGoalieGame], games: Sequence[NhlGame],
) -> list[NhlSkaterGame | NhlGoalieGame]:
    by_id = {game.game_id: game for game in games}
    latest = {row.player_id: row for row in sorted(rows, key=lambda row: by_id[row.game_id].start_utc)}
    return list(latest.values())


async def store_games(
    db: AsyncSession, games: list[NhlGame], skaters: list[NhlSkaterGame], goalies: list[NhlGoalieGame],
) -> None:
    from app.repositories import nhl as repo

    names: dict[str, str] = {}
    for game in sorted(games, key=lambda game: game.start_utc):
        names[game.home_team] = game.home_team_name
        names[game.away_team] = game.away_team_name
    team_ids = {code: await repo.upsert_team(db, code, name) for code, name in sorted(names.items())}
    game_ids = await repo.upsert_games(db, games, team_ids)
    players = [
        repo.NhlPlayerRow(row.player_id, row.player_name, row.position, team_ids[row.team])
        for row in latest_player_rows([*skaters, *goalies], games)
    ]
    player_ids = await repo.upsert_players(db, players)
    await repo.upsert_skater_games(db, skaters, player_ids, game_ids, team_ids)
    await repo.upsert_goalie_games(db, goalies, player_ids, game_ids, team_ids)


async def run(season: int, days_back: int | None, dry_run: bool = False, today: date | None = None) -> IngestSummary:
    today = today or datetime.now(EASTERN).date()
    if season < 2023 or season > current_nhl_season(today):
        raise ValueError("NHL season must be between 2023 and the season in progress")
    if days_back is not None and days_back < 0:
        raise ValueError("days-back must be nonnegative")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        games, skipped, first, last = await fetch_schedule(client, season)
        first = max(first, today - timedelta(days=days_back)) if days_back is not None else first
        last = min(last, today)
        skaters, goalies, counts = await fetch_stats(client, season, first, last)
    skipped.update(counts)
    skaters, counts = select_stat_rows(skaters, games, first, last, "skater")
    skipped.update(counts)
    goalies, counts = select_stat_rows(goalies, games, first, last, "goalie")
    skipped.update(counts)
    summary = IngestSummary(
        season=season, games=len(games), skater_games=len(skaters), goalie_games=len(goalies),
        players=len({row.player_id for row in [*skaters, *goalies]}),
        teams=len({game.home_team for game in games} | {game.away_team for game in games}), skipped=skipped,
    )
    if not dry_run:
        from app.db.pool import SessionLocal

        async with SessionLocal() as db, db.begin():
            await store_games(db, games, skaters, goalies)
    return summary


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Load NHL schedules and skater/goalie box scores")
    parser.add_argument("--season", type=int, help="start year to backfill in full (2023 = 2023-24)")
    parser.add_argument("--days-back", type=int, default=3, help="without --season, refresh box scores from N days ago")
    parser.add_argument("--dry-run", action="store_true", help="fetch and count without database writes")
    args = parser.parse_args()
    season = args.season if args.season is not None else current_nhl_season(datetime.now(EASTERN).date())
    try:
        summary = await run(season, None if args.season is not None else args.days_back, args.dry_run)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        print(f"NHL ingest failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    verb = "would load" if args.dry_run else "loaded"
    print(
        f"NHL {verb} {summary.games} games, {summary.skater_games} skater-game rows, "
        f"{summary.goalie_games} goalie-game rows, {summary.players} players and {summary.teams} teams "
        f"for the {season} season"
    )
    print("Skipped: " + (", ".join(f"{key} {value}" for key, value in sorted(summary.skipped.items())) or "none"))


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
