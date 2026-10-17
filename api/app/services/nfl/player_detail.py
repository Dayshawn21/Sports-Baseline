"""The NFL player page's data, as of the current week.

This week's prop lines come from the slate the page already reads, so this never
calls `build_slate`. Display only; nothing here feeds a projection, edge or rank.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_line_grading import LineResult, settle_line
from app.core.nfl_player import (
    PlayerGameRow, PositionFocus, StatLine, focus_for, past_line_counts, record_splits, season_summary,
)
from app.core.prop_ranking_rule import BREAK_EVEN_BY_ODDS_TYPE
from app.nfl.markets import STANDARD_ODDS_TYPE, NflPropSegment
from app.repositories import nfl as nfl_repo
from app.schemas.nfl import (
    NflPastLineCountSchema, NflPlayerDetailResponse, NflPlayerGameSchema, NflPlayerSplitSchema,
    NflPlayerSummarySchema, NflPlayerUsageSchema, NflSeasonWeekSchema,
)

PREVIOUS_SEASON_GAMES = 5
USAGE_GAMES = 8
_DECIDED = ("over", "under", "push")


async def build_player_detail(db: AsyncSession, player_id: int, now: datetime) -> NflPlayerDetailResponse | None:
    current = await nfl_repo.get_current_week(db, now)
    if current is None:
        return None
    season, week = current
    profile = await nfl_repo.get_player_profile(db, player_id, season, week)
    if profile is None:
        return None
    rows = await nfl_repo.get_player_game_rows(db, player_id, season)
    lines = await nfl_repo.get_gradeable_prop_lines(db, season, player_id=player_id)
    return player_detail(profile, rows, [settle_line(line) for line in lines], season, week)


def player_detail(
    profile: dict, rows: Sequence[PlayerGameRow], results: Iterable[LineResult], season: int, week: int,
) -> NflPlayerDetailResponse:
    focus = focus_for(profile["position"])
    summary = season_summary(rows, season, focus)
    results = list(results)
    focus_lines = _focus_lines(results, focus)
    stats_through = (
        NflSeasonWeekSchema(season=profile["stats_season"], week=profile["stats_week"])
        if profile["stats_season"] is not None else None
    )
    return NflPlayerDetailResponse(
        player_id=profile["id"], name=profile["name"], position=profile["position"], team=profile["team_code"],
        season=season, week=week,
        depth_position=profile["depth_position"], depth_rank=profile["depth_rank"],
        injury_status=profile["report_status"], practice_status=profile["practice_status"],
        injury=profile["primary_injury"], aliases=list(profile["aliases"] or []),
        stats_through=stats_through,
        focus_market=focus.market.value if focus.market is not None else None,
        summary=NflPlayerSummarySchema(**_means(summary)),
        game_log=[_game(row, focus_lines.get(row.game_id)) for row in game_log_rows(rows, season)],
        usage_stats=list(focus.usage_stats),
        usage=[_usage(row, season) for row in reversed(rows[:USAGE_GAMES])],
        past_lines=[
            NflPastLineCountSchema(market=count.market, overs=count.overs, decided=count.decided)
            for count in past_line_counts(results)
        ],
        splits=[NflPlayerSplitSchema(label=split.label, **_means(split)) for split in record_splits(rows, focus)],
        break_even=BREAK_EVEN_BY_ODDS_TYPE[STANDARD_ODDS_TYPE],
    )


def _means(line: StatLine) -> dict[str, int | float | None]:
    return {
        "games": line.games, "focus_per_game": line.focus_per_game,
        "volume_per_game": line.volume_per_game, "snap_share": line.snap_share,
    }


def _usage(row: PlayerGameRow, season: int) -> NflPlayerUsageSchema:
    return NflPlayerUsageSchema(
        season=row.season, week=row.week, previous_season=row.season < season,
        passing_attempts=row.passing_attempts, rushing_attempts=row.rushing_attempts,
        targets=row.targets, receptions=row.receptions, snap_pct=row.snap_pct,
    )


def game_log_rows(rows: Sequence[PlayerGameRow], season: int) -> list[PlayerGameRow]:
    """This season's games plus the latest few of the previous one, newest first."""
    current = [row for row in rows if row.season == season]
    previous = [row for row in rows if row.season == season - 1][:PREVIOUS_SEASON_GAMES]
    return current + previous


def _focus_lines(results: Iterable[LineResult], focus: PositionFocus) -> dict[int, LineResult]:
    """Each game's settled focus-market line; the latest pre-kickoff snapshot wins if a game has two props."""
    if focus.market is None:
        return {}
    by_game: dict[int, LineResult] = {}
    for result in results:
        line = result.line
        if (line.market != focus.market or line.odds_type != STANDARD_ODDS_TYPE
                or line.segment != NflPropSegment.FULL_GAME or result.outcome not in _DECIDED):
            continue
        kept = by_game.get(line.game_id)
        if kept is None or (line.fetched_at, line.line_id) > (kept.line.fetched_at, kept.line.line_id):
            by_game[line.game_id] = result
    return by_game


def _game(row: PlayerGameRow, focus_line: LineResult | None) -> NflPlayerGameSchema:
    return NflPlayerGameSchema(
        game_id=row.game_id, season=row.season, week=row.week, opponent=row.opponent, is_home=row.is_home,
        team_score=row.team_score, opponent_score=row.opponent_score, snap_pct=row.snap_pct,
        passing_completions=row.passing_completions, passing_attempts=row.passing_attempts,
        passing_yards=row.passing_yards, rushing_attempts=row.rushing_attempts, rushing_yards=row.rushing_yards,
        targets=row.targets, receptions=row.receptions, receiving_yards=row.receiving_yards,
        touchdowns=row.touchdowns, prizepicks_fantasy_points=row.prizepicks_fantasy_points,
        focus_line=focus_line.line.line if focus_line is not None else None,
        focus_outcome=focus_line.outcome if focus_line is not None else None,
    )
