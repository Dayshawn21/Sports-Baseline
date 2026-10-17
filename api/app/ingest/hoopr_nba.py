"""NBA schedules and per-game player box scores from hoopR's ESPN release files.

sportsdataverse publishes them as public GitHub release assets, named by the
year a season ends. ESPN ids key every game, team and player (item 20a). This
module fetches and normalizes; persistence lives in `app.repositories.nba`.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from io import StringIO

import httpx

from app.core.nba_season import (
    REGULAR_SEASON,
    current_nba_season,
    file_season,
    game_type,
    nba_week,
    opening_night,
    stored_season,
)

HOOPR_RELEASE_BASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"
# ESPN's placeholder for an NBA Cup knockout slot whose teams are not set yet.
PLACEHOLDER_TEAM = "TBD"
# A postponed game is replayed under a new ESPN game id, so the original row
# never finishes; storing it as postponed keeps its week from waiting on it.
_ESPN_STATUSES = {"STATUS_POSTPONED": "postponed", "STATUS_CANCELED": "canceled"}
# ESPN files the All-Star games (Stars, Stripes, World teams) as regular season.
ALL_STAR_TYPE = "ALLSTAR"


class SeasonNotPublished(Exception):
    """hoopR has no schedule asset for the requested season."""

    def __init__(self, season: int) -> None:
        super().__init__(f"hoopR has not published an NBA schedule for the {season}-{(season + 1) % 100:02d} season")


class BoxScoresMissing(Exception):
    """Games are final but hoopR has no box-score asset for their season."""


@dataclass(frozen=True)
class NbaGame:
    game_id: str
    season: int
    week: int | None
    game_type: str
    game_date: date
    start_utc: datetime | None
    home_team: str
    home_team_name: str
    away_team: str
    away_team_name: str
    home_score: int | None
    away_score: int | None
    status: str


@dataclass(frozen=True)
class NbaPlayerGame:
    game_id: str
    player_id: str
    player_name: str
    position: str | None
    team: str
    opponent: str
    season: int
    is_home: bool
    starter: bool
    did_not_play: bool
    dnp_reason: str | None
    minutes: float | None
    points: int | None
    rebounds: int | None
    offensive_rebounds: int | None
    defensive_rebounds: int | None
    assists: int | None
    steals: int | None
    blocks: int | None
    turnovers: int | None
    fouls: int | None
    field_goals_made: int | None
    field_goals_attempted: int | None
    three_pointers_made: int | None
    three_pointers_attempted: int | None
    free_throws_made: int | None
    free_throws_attempted: int | None
    plus_minus: int | None


def schedule_url(file_season: int) -> str:
    return f"{HOOPR_RELEASE_BASE}/espn_nba_schedules/nba_schedule_{file_season}.csv"


def player_box_url(file_season: int) -> str:
    return f"{HOOPR_RELEASE_BASE}/espn_nba_player_boxscores/player_box_{file_season}.csv"


def _blank(value: str | None) -> bool:
    return value is None or value.strip() in ("", "NA")


def _int(value: str | None) -> int | None:
    # plus_minus arrives signed ("+2"); int() accepts the sign.
    return None if _blank(value) else int(float(value))


def _float(value: str | None) -> float | None:
    return None if _blank(value) else float(value)


def _bool(value: str | None) -> bool:
    return (value or "").strip().lower() == "true"


def _text(value: str | None) -> str | None:
    return None if _blank(value) else value.strip()


def _status(row: dict[str, str]) -> str:
    if _bool(row.get("status_type_completed")):
        return "completed"
    return _ESPN_STATUSES.get((row.get("status_type_name") or "").strip(), "scheduled")


def _start_utc(value: str | None) -> datetime | None:
    if _blank(value):
        return None
    return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))


def parse_schedule(csv_text: str) -> tuple[list[NbaGame], Counter[str]]:
    """Games plus skip counts. Weeks need the whole season's opening night, so rows are read first."""
    skipped: Counter[str] = Counter()
    kept: list[tuple[dict[str, str], str]] = []
    for row in csv.DictReader(StringIO(csv_text)):
        kind = game_type(int(row["season_type"])) if not _blank(row.get("season_type")) else None
        if kind is None:
            skipped["not_regular_or_postseason"] += 1
        elif _blank(row.get("game_id")):
            skipped["missing_game_id"] += 1
        elif (row.get("type_abbreviation") or "").strip() == ALL_STAR_TYPE:
            skipped["all_star"] += 1
        elif PLACEHOLDER_TEAM in (row["home_abbreviation"], row["away_abbreviation"]):
            skipped["placeholder_team"] += 1
        else:
            kept.append((row, kind))

    regular_dates = [date.fromisoformat(row["game_date"]) for row, kind in kept if kind == REGULAR_SEASON]
    opening = opening_night(regular_dates) if regular_dates else None
    games = []
    for row, kind in kept:
        game_date = date.fromisoformat(row["game_date"])
        status = _status(row)
        completed = status == "completed"
        games.append(NbaGame(
            game_id=row["game_id"].strip(),
            season=stored_season(int(row["season"])),
            week=nba_week(game_date, opening) if kind == REGULAR_SEASON and opening else None,
            game_type=kind,
            game_date=game_date,
            start_utc=_start_utc(row.get("start_date")),
            home_team=row["home_abbreviation"].strip(),
            home_team_name=row["home_display_name"].strip(),
            away_team=row["away_abbreviation"].strip(),
            away_team_name=row["away_display_name"].strip(),
            home_score=_int(row.get("home_score")) if completed else None,
            away_score=_int(row.get("away_score")) if completed else None,
            status=status,
        ))
    return games, skipped


def parse_player_box(csv_text: str) -> tuple[list[NbaPlayerGame], Counter[str]]:
    """Player-game rows plus skip counts. A DNP row keeps its NULL stats; nothing becomes zero."""
    skipped: Counter[str] = Counter()
    rows = []
    for row in csv.DictReader(StringIO(csv_text)):
        if _blank(row.get("athlete_id")):
            skipped["missing_athlete_id"] += 1
            continue
        if _blank(row.get("game_id")):
            skipped["missing_game_id"] += 1
            continue
        rows.append(NbaPlayerGame(
            game_id=row["game_id"].strip(),
            player_id=row["athlete_id"].strip(),
            player_name=row["athlete_display_name"].strip(),
            position=_text(row.get("athlete_position_abbreviation")),
            team=row["team_abbreviation"].strip(),
            opponent=row["opponent_team_abbreviation"].strip(),
            season=stored_season(int(row["season"])),
            is_home=row.get("home_away", "").strip().lower() == "home",
            starter=_bool(row.get("starter")),
            did_not_play=_bool(row.get("did_not_play")),
            # ESPN fills `reason` for players who played too; it means something only on a DNP.
            dnp_reason=_text(row.get("reason")) if _bool(row.get("did_not_play")) else None,
            minutes=_float(row.get("minutes")),
            points=_int(row.get("points")),
            rebounds=_int(row.get("rebounds")),
            offensive_rebounds=_int(row.get("offensive_rebounds")),
            defensive_rebounds=_int(row.get("defensive_rebounds")),
            assists=_int(row.get("assists")),
            steals=_int(row.get("steals")),
            blocks=_int(row.get("blocks")),
            turnovers=_int(row.get("turnovers")),
            fouls=_int(row.get("fouls")),
            field_goals_made=_int(row.get("field_goals_made")),
            field_goals_attempted=_int(row.get("field_goals_attempted")),
            three_pointers_made=_int(row.get("three_point_field_goals_made")),
            three_pointers_attempted=_int(row.get("three_point_field_goals_attempted")),
            free_throws_made=_int(row.get("free_throws_made")),
            free_throws_attempted=_int(row.get("free_throws_attempted")),
            plus_minus=_int(row.get("plus_minus")),
        ))
    return rows, skipped


@dataclass
class IngestSummary:
    season: int
    games: int = 0
    player_games: int = 0
    players: int = 0
    teams: int = 0
    box_scores_published: bool = True
    skipped: Counter[str] = field(default_factory=Counter)


def select_player_games(
    rows: list[NbaPlayerGame], games: list[NbaGame], since: date | None,
) -> tuple[list[NbaPlayerGame], Counter[str]]:
    """Box-score rows for stored games, optionally only games dated on or after `since`."""
    skipped: Counter[str] = Counter()
    by_id = {game.game_id: game for game in games}
    teams = {game.home_team for game in games} | {game.away_team for game in games}
    selected = []
    for row in rows:
        game = by_id.get(row.game_id)
        if game is None:
            skipped["box_game_not_stored"] += 1
        elif row.team not in teams or row.opponent not in teams:
            skipped["box_team_unknown"] += 1
        elif since is None or game.game_date >= since:
            selected.append(row)
    return selected, skipped


def latest_teams(rows: list[NbaPlayerGame], games: list[NbaGame]) -> dict[str, str]:
    """Each player's team in their most recent game, for `sport_players.team_id`."""
    game_dates = {game.game_id: game.game_date for game in games}
    latest: dict[str, tuple[date, str]] = {}
    for row in rows:
        played = game_dates[row.game_id]
        if row.player_id not in latest or played >= latest[row.player_id][0]:
            latest[row.player_id] = (played, row.team)
    return {player_id: team for player_id, (_, team) in latest.items()}


async def fetch_season(client: httpx.AsyncClient, season: int) -> tuple[str, str | None]:
    """Schedule and box-score CSV text; the box text is None while hoopR has not published it."""
    schedule = await client.get(schedule_url(file_season(season)), timeout=120)
    if schedule.status_code == 404:
        raise SeasonNotPublished(season)
    schedule.raise_for_status()
    box = await client.get(player_box_url(file_season(season)), timeout=300)
    if box.status_code == 404:
        return schedule.text, None
    box.raise_for_status()
    return schedule.text, box.text


async def store_games(db, games: list[NbaGame], rows: list[NbaPlayerGame], summary: IngestSummary) -> None:
    from app.repositories import nba as nba_repo

    names = {game.home_team: game.home_team_name for game in games}
    names.update({game.away_team: game.away_team_name for game in games})
    team_ids = {code: await nba_repo.upsert_team(db, code, name) for code, name in sorted(names.items())}
    game_ids = await nba_repo.upsert_games(db, games, team_ids)
    latest_row = {row.player_id: row for row in rows}
    players = [
        nba_repo.NbaPlayerRow(player_id, latest_row[player_id].player_name, latest_row[player_id].position, team_ids[team])
        for player_id, team in latest_teams(rows, games).items()
    ]
    player_ids = await nba_repo.upsert_players(db, players)
    summary.teams, summary.games, summary.players = len(team_ids), len(game_ids), len(player_ids)
    summary.player_games = await nba_repo.upsert_player_games(db, rows, player_ids, game_ids, team_ids)


async def run(season: int, days_back: int | None, dry_run: bool = False, today: date | None = None) -> IngestSummary:
    """Fetch and parse a season, then upsert it in one transaction.

    `days_back` limits box scores to recent games for the daily refresh; None
    loads every box score (a backfill). The whole schedule is always upserted.
    """
    from app.db.pool import SessionLocal

    async with httpx.AsyncClient(follow_redirects=True) as client:
        schedule_text, box_text = await fetch_season(client, season)
    games, skipped = parse_schedule(schedule_text)
    summary = IngestSummary(season=season, skipped=skipped)
    rows: list[NbaPlayerGame] = []
    if box_text is None:
        if any(game.status == "completed" for game in games):
            raise BoxScoresMissing(f"The {season} season has final games but no published box scores")
        summary.box_scores_published = False
    else:
        parsed, box_skipped = parse_player_box(box_text)
        since = (today or date.today()) - timedelta(days=days_back) if days_back is not None else None
        rows, select_skipped = select_player_games(parsed, games, since)
        summary.skipped.update(box_skipped)
        summary.skipped.update(select_skipped)
    if dry_run:
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
    parser = argparse.ArgumentParser(description="Load NBA schedules and player box scores from hoopR's ESPN files")
    parser.add_argument(
        "--season", type=int, default=None,
        help="season start year to backfill in full (2025 = 2025-26); defaults to the season in progress",
    )
    parser.add_argument(
        "--days-back", type=int, default=3,
        help="without --season, load box scores for games in the last N days",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    backfill = args.season is not None
    season = args.season if backfill else current_nba_season(date.today())
    try:
        summary = await run(season, None if backfill else args.days_back, args.dry_run)
    except (SeasonNotPublished, BoxScoresMissing) as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1)
    verb = "would load" if args.dry_run else "loaded"
    print(
        f"hoopR NBA {verb} {summary.games} games, {summary.player_games} player-game rows "
        f"and {summary.players} players for the {season} season"
    )
    if not summary.box_scores_published:
        print(f"No box scores published for the {season} season yet; no game is final, so this is expected.")
    if summary.skipped:
        print("Skipped: " + ", ".join(f"{reason} {count}" for reason, count in sorted(summary.skipped.items())))


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
