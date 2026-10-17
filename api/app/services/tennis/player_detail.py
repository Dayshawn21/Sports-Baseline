"""Everything the tennis player page shows about one player (build-plan 32c)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.box_score_join import BoxScoreCandidate, JoinResult
from app.core.prop_projection import normalize_stat_type
from app.core.prop_settlement import resolve_actual, settle
from app.core.tennis_grading import is_completed_score
from app.core.tennis_player import (
    RECORD_WINDOW_DAYS,
    AverageStats,
    EloSnapshot,
    EloSummary,
    PlayerMatchRow,
    RecordSplits,
    ServeReturnStats,
    elo_summary,
    record_splits,
    tour_average,
)
from app.repositories import matches as match_repo
from app.repositories import player_match_stats as box_score_repo
from app.repositories import prop_snapshots as prop_snapshot_repo
from app.repositories import players as player_repo
from app.repositories.matches import NextMatch, PlayerMatchLogRow
from app.repositories.players import PlayerHeader, SurfaceServeReturnRow
from app.repositories.prop_snapshots import GradedPropSnapshot
from app.services.tennis.prop_snapshots import PROJECTION_VERSION


@dataclass(frozen=True)
class PlayerEloDetail:
    summary: EloSummary
    history: list[EloSnapshot]
    tour_rank: Optional[int]
    tour_rank_of: Optional[int]


@dataclass(frozen=True)
class PlayerDetail:
    header: PlayerHeader
    rank: Optional[int]
    elo: PlayerEloDetail
    next_match: Optional[NextMatch]
    aliases: list[str]
    stats_computed_at: Optional[datetime]


async def build_player_detail(db: AsyncSession, player_id: int, today: date) -> Optional[PlayerDetail]:
    header = await player_repo.get_player_header(db, player_id)
    if header is None:
        return None
    history = await player_repo.get_elo_history(db, player_id)
    summary = elo_summary(history)
    tour_rank = tour_rank_of = None
    if summary.latest is not None:
        tour_rank, tour_rank_of = await player_repo.get_elo_tour_rank(
            db, player_id, header.tour, summary.latest.as_of,
        )
    return PlayerDetail(
        header=header,
        rank=await match_repo.get_latest_rank(db, player_id),
        elo=PlayerEloDetail(summary, history, tour_rank, tour_rank_of),
        next_match=await match_repo.get_next_match(db, player_id, today),
        aliases=await player_repo.get_player_aliases(db, player_id),
        stats_computed_at=await player_repo.get_rolling_stats_computed_at(db, player_id),
    )


# The same floor the slate uses before trusting a player's surface split.
TOUR_AVERAGE_MIN_MATCHES = 10
SURFACE_KEYS: tuple[Optional[str], ...] = (None, "Hard", "Clay", "Grass")


@dataclass(frozen=True)
class SurfaceComparison:
    surface: str
    """"all", "Hard", "Clay" or "Grass"."""
    player_matches: Optional[int]
    player: Optional[ServeReturnStats]
    tour_average: AverageStats


@dataclass(frozen=True)
class PlayerServeReturn:
    tour: str
    surfaces: list[SurfaceComparison]


def compare_serve_return(player_id: int, tour: str, rows: list[SurfaceServeReturnRow]) -> PlayerServeReturn:
    surfaces = []
    for key in SURFACE_KEYS:
        on_surface = [r for r in rows if r.surface == key]
        mine = next((r for r in on_surface if r.player_id == player_id), None)
        average = tour_average([(r.matches, r.stats) for r in on_surface], TOUR_AVERAGE_MIN_MATCHES)
        surfaces.append(SurfaceComparison(
            key or "all", mine.matches if mine else None, mine.stats if mine else None, average,
        ))
    return PlayerServeReturn(tour, surfaces)


async def build_serve_return(db: AsyncSession, player_id: int) -> Optional[PlayerServeReturn]:
    header = await player_repo.get_player_header(db, player_id)
    if header is None:
        return None
    rows = await player_repo.get_tour_serve_return_rows(db, header.tour)
    return compare_serve_return(player_id, header.tour, rows)


@dataclass(frozen=True)
class MatchLogEntry:
    match: PlayerMatchLogRow
    box: Optional[BoxScoreCandidate]


@dataclass(frozen=True)
class PlayerMatches:
    log: list[MatchLogEntry]
    record: RecordSplits


def record_row(row: PlayerMatchLogRow) -> PlayerMatchRow:
    return PlayerMatchRow(row.match_date, row.surface, row.best_of, row.won, row.score, row.opponent_rank)


async def build_player_matches(
    db: AsyncSession, player_id: int, limit: int, today: date,
) -> Optional[PlayerMatches]:
    if await player_repo.get_player_header(db, player_id) is None:
        return None
    # The record reads its whole window, not the capped log, so a limit of 5
    # never shrinks the 52-week splits.
    window = await match_repo.get_player_matches(db, player_id, since=today - timedelta(days=RECORD_WINDOW_DAYS))
    return PlayerMatches(
        log=await _match_log(db, player_id, limit),
        record=record_splits([record_row(r) for r in window], today),
    )


async def _match_log(db: AsyncSession, player_id: int, limit: int) -> list[MatchLogEntry]:
    rows = await match_repo.get_player_matches(db, player_id, limit=limit)
    # join_box_score matches on opponent and set score, never on date: box scores
    # are dated by tournament start.
    contexts = await box_score_repo.get_box_score_candidates(db, [(player_id, r.match_id) for r in rows])
    entries = []
    for row in rows:
        context = contexts.get((player_id, row.match_id))
        joined = context.join() if context else None
        entries.append(MatchLogEntry(row, joined.candidate if joined else None))
    return entries


PropOutcome = Literal["hit", "miss", "push", "pass", "void", "awaiting", "ungradable"]


@dataclass(frozen=True)
class PastProp:
    snapshot_date: date
    stat: str
    odds_type: str
    line: float
    actual: Optional[int]
    recommendation: Optional[str]
    confidence: Optional[str]
    outcome: PropOutcome


@dataclass(frozen=True)
class PlayerProps:
    projection_version: str
    rows: list[PastProp]
    hits: int
    misses: int
    """Standard lines with a recommendation only, as 26f and 32b grade them."""


def past_prop(row: GradedPropSnapshot, join: Optional[JoinResult]) -> PastProp:
    stat = normalize_stat_type(row.stat_type)
    odds_type = (row.odds_type or "standard").lower()
    actual: Optional[int] = None
    if not is_completed_score(row.score, row.best_of or 3):
        outcome: PropOutcome = "void"
    else:
        actual, reason = resolve_actual(stat, row.score, row.player_is_p1, join)
        if actual is None:
            # A stat with no settlement source (fantasy score) will never settle;
            # a box-score stat can still land after the next refetch.
            outcome = "ungradable" if reason == "not_settleable" else "awaiting"
        elif row.recommendation is None:
            outcome = "pass"
        else:
            settled = settle(actual, row.line)
            outcome = "push" if settled == "push" else ("hit" if settled == row.recommendation.lower() else "miss")
    snapshot_date = row.snapshot_at.astimezone(UTC).date() if row.snapshot_at else date.min
    return PastProp(snapshot_date, stat, odds_type, row.line, actual, row.recommendation, row.confidence, outcome)


async def build_player_props(db: AsyncSession, player_id: int) -> Optional[PlayerProps]:
    if await player_repo.get_player_header(db, player_id) is None:
        return None
    snapshots = await prop_snapshot_repo.get_graded_prop_snapshots(db, PROJECTION_VERSION, player_id=player_id)
    contexts = await box_score_repo.get_box_score_candidates(db, sorted({(s.player_id, s.match_id) for s in snapshots}))
    rows = []
    for snapshot in snapshots:
        context = contexts.get((snapshot.player_id, snapshot.match_id))
        rows.append(past_prop(snapshot, context.join() if context else None))
    rows.sort(key=lambda p: (p.snapshot_date, p.stat, p.line), reverse=True)
    graded = [r for r in rows if r.odds_type == "standard" and r.outcome in ("hit", "miss")]
    return PlayerProps(
        PROJECTION_VERSION, rows,
        hits=sum(r.outcome == "hit" for r in graded),
        misses=sum(r.outcome == "miss" for r in graded),
    )
