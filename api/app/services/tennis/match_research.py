"""Current display snapshots and pre-match workload, separate from prediction inputs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tennis_match_context import ResearchStats, Workload, return_rate, valid_rate, workload
from app.repositories import players as player_repo
from app.repositories import tennis_match_context as context_repo
from app.repositories.matches import Match
from app.repositories.players import PlayerElo, PlayerRollingStats
from app.repositories.tennis_match_context import BookFreshness


@dataclass(frozen=True)
class PlayerResearch:
    player_id: int
    elo_as_of_date: date | None
    surface_stats: ResearchStats | None
    overall_stats: ResearchStats | None
    workload: Workload


@dataclass(frozen=True)
class MatchResearch:
    players: list[PlayerResearch]
    odds: list[BookFreshness]
    odds_cutoff: str = "Before scheduled start when known"
    elo_source: str = "TennisAbstract; latest available ratings"


def research_stats(stats: PlayerRollingStats | None) -> ResearchStats | None:
    if stats is None:
        return None
    return ResearchStats(
        surface=stats.surface, matches_count=stats.matches_count, computed_at=stats.computed_at,
        win_rate=valid_rate(stats.win_rate), hold_pct=valid_rate(stats.hold_pct),
        return_points_won=valid_rate(stats.ret_pts_won), break_conversion_pct=valid_rate(stats.break_pct),
        first_in_pct=valid_rate(stats.first_in_pct), first_serve_won=valid_rate(stats.first_won_pct),
        second_serve_won=valid_rate(stats.second_won_pct),
        first_return_won=return_rate(stats.allowed_first_won_pct),
        second_return_won=return_rate(stats.allowed_second_won_pct),
        thin_sample=(stats.matches_count or 0) < 10,
    )


async def build_match_research(db: AsyncSession, match: Match, elos: dict[int, PlayerElo]) -> MatchResearch:
    ids = [match.p1_id, match.p2_id]
    stats = await player_repo.get_rolling_stats_batch_all_surfaces(db, ids, "last_52w")
    history = await context_repo.get_workload_matches(db, ids, match.match_date)
    odds = await context_repo.get_book_freshness(db, match.id, match.start_utc)
    return MatchResearch([
        PlayerResearch(
            player_id=pid, elo_as_of_date=elos[pid].as_of_date if pid in elos else None,
            surface_stats=research_stats(stats.get((pid, match.surface))) if match.surface else None,
            overall_stats=research_stats(stats.get((pid, None))),
            workload=workload(history.get(pid, []), match.id, match.match_date),
        ) for pid in ids
    ], odds)
