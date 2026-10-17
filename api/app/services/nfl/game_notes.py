"""Per-game pre-bet notes for the NFL slate: injuries, depth moves, line movement, form, team stats.

Kept apart from `build_slate`, which the 27a grading and 27i frozen predictions
replay, so this display-only context adds nothing to those runs.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_availability import NflAvailability
from app.core.nfl_best_line import MAX_AGE_HOURS, Quote, best_lines
from app.core.nfl_game_notes import depth_change, injury_sort_key, line_move, result, short_week, worth_listing
from app.core.nfl_qb_change import USUAL_STARTER_GAMES, QbChange, qb_change
from app.core.nfl_team_stats import EMPTY_TEAM_STATS, TeamStats, team_stats
from app.repositories import nfl as nfl_repo
from app.schemas.nfl import (
    NflBestLineSchema,
    NflBestMarketSchema,
    NflBestSideSchema,
    NflFairPriceSchema,
    NflGameNotesResponse,
    NflGameNotesSchema,
    NflLineMoveSchema,
    NflNoteDepthChangeSchema,
    NflNoteInjurySchema,
    NflQbChangeSchema,
    NflRecentResultSchema,
    NflTeamFormSchema,
    NflTeamStatSchema,
    NflTeamStatsSchema,
)

_AVAILABILITY_FIELDS = tuple(NflAvailability.__dataclass_fields__)


async def build_game_notes(db: AsyncSession, season: int, week: int) -> NflGameNotesResponse:
    games = await nfl_repo.get_week_game_rest(db, season, week)
    injuries = await nfl_repo.get_week_skill_injuries(db, season, week)
    depth_rows = await nfl_repo.get_week_depth_rows(db, season, week)
    moves = await nfl_repo.get_week_line_movement(db, season, week)
    recent = await nfl_repo.get_week_team_recent_results(db, season, week)
    stats = team_stats(await nfl_repo.get_week_team_games(db, season, week))
    qb_changes = await _week_qb_changes(db, season, week)
    quotes = await nfl_repo.get_week_game_quotes(db, season, week)
    now = datetime.now(UTC)
    best = {game_id: best_line_schema(start_utc, game_quotes, now) for game_id, (start_utc, game_quotes) in quotes.items()}
    return NflGameNotesResponse(
        season=season, week=week,
        games=[
            game_notes(game_id, game, injuries, depth_rows, moves, recent, stats, qb_changes, best.get(game_id))
            for game_id, game in sorted(games.items())
        ],
    )


def game_notes(
    game_id: int,
    game: dict,
    injuries: list[dict],
    depth_rows: list[dict],
    moves: list[dict],
    recent: dict[int, list[dict]],
    stats: dict[int, TeamStats],
    qb_changes: dict[int, QbChange] | None = None,
    best_line: NflBestLineSchema | None = None,
) -> NflGameNotesSchema:
    team_ids = {game["away_team_id"], game["home_team_id"]}
    listed = sorted(
        (row for row in injuries if row["team_id"] in team_ids and worth_listing(row["injury_status"], row["practice_status"])),
        key=lambda row: injury_sort_key(row["injury_status"], row["position"], row["player_name"]),
    )
    return NflGameNotesSchema(
        game_id=game_id, away_team=game["away_team"], home_team=game["home_team"],
        injuries=[NflNoteInjurySchema(**{key: value for key, value in row.items() if key != "team_id"}) for row in listed],
        depth_changes=_depth_changes([row for row in depth_rows if row["team_id"] in team_ids]),
        line_movement=[_line_move(row) for row in moves if row["game_id"] == game_id],
        away_form=_team_form(game["away_team"], game["away_rest"], recent.get(game["away_team_id"], [])),
        home_form=_team_form(game["home_team"], game["home_rest"], recent.get(game["home_team_id"], [])),
        away_stats=_team_stats(game["away_team"], stats.get(game["away_team_id"], EMPTY_TEAM_STATS)),
        home_stats=_team_stats(game["home_team"], stats.get(game["home_team_id"], EMPTY_TEAM_STATS)),
        away_score=game["away_score"], home_score=game["home_score"],
        away_qb_change=_qb_change_schema(game["away_team"], (qb_changes or {}).get(game["away_team_id"])),
        home_qb_change=_qb_change_schema(game["home_team"], (qb_changes or {}).get(game["home_team_id"])),
        best_line=best_line,
    )


def best_line_schema(start_utc: datetime | None, quotes: list[Quote], now: datetime) -> NflBestLineSchema | None:
    """Null once the game kicks off, so a closed price never reads as available."""
    if start_utc is not None and start_utc <= now:
        return None
    markets = best_lines(quotes, now)
    if not markets:
        return None
    return NflBestLineSchema(max_age_hours=MAX_AGE_HOURS, markets=[
        NflBestMarketSchema(
            market=market.market,
            fair=NflFairPriceSchema(**asdict(market.fair)) if market.fair else None,
            sides=[NflBestSideSchema(**asdict(side) | {
                "ev_pct": None if side.ev_pct is None else round(side.ev_pct, 4),
                "points_vs_fair": None if side.points_vs_fair is None else round(side.points_vs_fair, 1),
            }) for side in market.sides],
        )
        for market in markets
    ])


async def _week_qb_changes(db: AsyncSession, season: int, week: int) -> dict[int, QbChange]:
    """Each week team's QB change, from the latest stored chart, injury report and box scores."""
    games = await nfl_repo.get_week_team_qb_games(db, season, week, USUAL_STARTER_GAMES)
    charts = await nfl_repo.get_week_team_qb1_charts(db, season, week)
    injuries = await nfl_repo.get_week_team_qb_injuries(db, season, week)
    changes = {}
    for team_id in games.keys() | charts.keys():
        latest_qb1, previous_qb1 = charts.get(team_id, (None, None))
        change = qb_change(games.get(team_id, []), injuries.get(team_id, {}), latest_qb1, previous_qb1)
        if change is not None:
            changes[team_id] = change
    return changes


def _qb_change_schema(team: str, change: QbChange | None) -> NflQbChangeSchema | None:
    if change is None:
        return None
    return NflQbChangeSchema(team=team, **asdict(change))


def _depth_changes(rows: list[dict]) -> list[NflNoteDepthChangeSchema]:
    changes = []
    for row in rows:
        change = depth_change(NflAvailability(**{field: row[field] for field in _AVAILABILITY_FIELDS if field in row}))
        if change is not None:
            changes.append(NflNoteDepthChangeSchema(
                player_id=row["player_id"], player_name=row["player_name"], team=row["team"],
                depth_position=row["depth_position"], depth_rank=row["depth_rank"],
                previous_depth_position=row["previous_depth_position"],
                previous_depth_rank=row["previous_depth_rank"], change=change,
            ))
    return sorted(changes, key=lambda item: (item.team, item.depth_position, item.depth_rank))


def _line_move(row: dict) -> NflLineMoveSchema:
    single_line = row["open_fetched_at"] == row["current_fetched_at"]
    return NflLineMoveSchema(
        **row | {"move": None if single_line else line_move(row["open_line"], row["current_line"])},
    )


def _team_form(team: str, rest_days: int | None, games: list[dict]) -> NflTeamFormSchema:
    return NflTeamFormSchema(
        team=team, rest_days=rest_days, short_week=short_week(rest_days),
        recent=[
            NflRecentResultSchema(**played, result=result(played["points_for"], played["points_against"]))
            for played in games
        ],
    )


def _team_stats(team: str, stats: TeamStats) -> NflTeamStatsSchema:
    return NflTeamStatsSchema(
        team=team, games=stats.games, efficiency_games=stats.efficiency_games,
        **{key: NflTeamStatSchema(value=line.value, rank=line.rank) for key, line in stats.stats.items()},
    )
