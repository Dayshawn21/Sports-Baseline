"""The admin repair queue: players in today's and tomorrow's matches whose ELO or stats flag a prediction."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ta_slug import ta_slug
from app.core.tennis_flag_queue import ELO_FLAGS, STATS_FLAG, missing_surfaces, refine_player_flags
from app.ml.registry import ModelRegistry
from app.repositories import matches as match_repo
from app.repositories import players as player_repo
from app.repositories.matches import Match
from app.services.tennis import predictor
from app.services.tennis.predictor import PredictionOutput

_TARGET_FLAGS = ELO_FLAGS | {STATS_FLAG}


@dataclass(frozen=True)
class FlaggedPlayerRow:
    player_id: int
    player_name: str
    tour: str
    flags: list[str]
    has_elo: bool
    has_stats: bool
    missing_surfaces: list[str]
    ta_slug: str | None
    auto_slug: str


@dataclass(frozen=True)
class CollectedFlags:
    flags: dict[int, set[str]]
    # Surfaces of the matches that flag a player for stats, so a surface row can clear it.
    surfaces: dict[int, set[str | None]]


def collect_flags(predictions: Iterable[PredictionOutput], match_map: Mapping[int, Match]) -> CollectedFlags:
    """Map each prediction's ELO and stats flags to the players that may cause them."""
    flagged: dict[int, set[str]] = {}
    surfaces: dict[int, set[str | None]] = {}

    for pred in predictions:
        m = match_map.get(pred.match_id)
        if not m:
            continue
        active_flags = set(pred.quality_flags) & _TARGET_FLAGS
        if not active_flags:
            continue

        for flag in active_flags:
            if flag == "p1_elo_missing":
                flagged.setdefault(m.p1_id, set()).add(flag)
            elif flag == "p2_elo_missing":
                flagged.setdefault(m.p2_id, set()).add(flag)
            elif flag == "elo_missing":
                # Both players missing ELO
                flagged.setdefault(m.p1_id, set()).add(flag)
                flagged.setdefault(m.p2_id, set()).add(flag)
            elif flag == STATS_FLAG:
                # Attribute to both; refine_player_flags keeps it only for whoever truly lacks stats
                for pid in (m.p1_id, m.p2_id):
                    flagged.setdefault(pid, set()).add(flag)
                    surfaces.setdefault(pid, set()).add(m.surface)

    return CollectedFlags(flags=flagged, surfaces=surfaces)


async def load_flagged_players(
    db: AsyncSession, registry: ModelRegistry, today: date
) -> list[FlaggedPlayerRow]:
    target_dates = [today, today + timedelta(days=1)]

    predictions = await predictor.predict_today(db, registry, target_dates)
    matches = await match_repo.get_upcoming(db, target_dates)
    collected = collect_flags(predictions, {m.id: m for m in matches})
    flagged, surfaces = collected.flags, collected.surfaces

    if not flagged:
        return []

    all_ids = list(flagged.keys())
    players_map = await player_repo.get_players_by_ids(db, all_ids)
    elo_map = await player_repo.get_latest_elo_batch(db, all_ids)
    # The same lookup the predictor uses, so (pid, None) is the all-surface row
    stats_map = await player_repo.get_rolling_stats_batch_all_surfaces(db, all_ids, "last_52w")
    stat_surfaces: dict[int, set[str | None]] = {}
    for stat_pid, stat_surface in stats_map:
        stat_surfaces.setdefault(stat_pid, set()).add(stat_surface)

    result: list[FlaggedPlayerRow] = []
    for pid, flags in flagged.items():
        player = players_map.get(pid)
        if not player:
            continue

        elo = elo_map.get(pid)
        stats = stats_map.get((pid, None))
        has_elo = elo is not None and elo.elo is not None
        refined_flags = refine_player_flags(
            flags,
            has_elo=has_elo,
            stat_surfaces=stat_surfaces.get(pid, set()),
            match_surfaces=surfaces.get(pid, set()),
        )

        if not refined_flags:
            continue

        result.append(FlaggedPlayerRow(
            player_id=pid,
            player_name=player.name,
            tour=player.tour,
            flags=sorted(refined_flags),
            has_elo=has_elo,
            has_stats=stats is not None,
            missing_surfaces=missing_surfaces(stat_surfaces.get(pid, set()), surfaces.get(pid, set())),
            ta_slug=player.ta_slug,
            auto_slug=ta_slug(player.name),
        ))

    return result
