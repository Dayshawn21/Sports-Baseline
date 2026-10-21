"""Immutable daily candidate snapshots, isolated from production player_elo."""
from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tennis_elo import Namespace, TennisEloRating

SOURCE = "tennismylife-elo-v1"
_COLUMNS = (
    "player_id", "source", "as_of_date", "overall", "hard", "clay", "grass",
    "overall_matches", "hard_matches", "clay_matches", "grass_matches",
    "provider_namespace", "provider_player_id", "computed_at", "source_downloaded_at",
    "replay_cutoff", "method_version", "manifest_sha256",
)


@dataclass(frozen=True)
class TennisEloSnapshot:
    player_id: int
    source: str
    as_of_date: date
    rating: TennisEloRating
    provider_namespace: Namespace
    provider_player_id: str
    computed_at: datetime
    source_downloaded_at: datetime
    replay_cutoff: date
    method_version: str
    manifest_sha256: str

    def __post_init__(self) -> None:
        if self.player_id < 1 or self.source != SOURCE or self.method_version != SOURCE:
            raise ValueError("Candidate ELO requires a player ID and the pinned v1 source/method")
        if self.provider_namespace not in {"ATP", "WTA"} or not re.fullmatch(r"[A-Za-z0-9]+", self.provider_player_id):
            raise ValueError("Invalid candidate ELO provider identity")
        if not re.fullmatch(r"[a-f0-9]{64}", self.manifest_sha256):
            raise ValueError("Candidate ELO requires a lowercase SHA-256 manifest digest")
        if any(t.utcoffset() is None for t in (self.computed_at, self.source_downloaded_at)):
            raise ValueError("Candidate ELO provenance timestamps must be timezone-aware")
        if (self.source_downloaded_at > self.computed_at or self.replay_cutoff != self.as_of_date
                or self.computed_at.astimezone(timezone.utc).date() != self.as_of_date):
            raise ValueError("Candidate ELO date/cutoff/provenance ordering is inconsistent")
        _validate_rating(self.rating)


def _validate_rating(rating: TennisEloRating) -> None:
    if not math.isfinite(rating.overall) or rating.overall_matches < 1:
        raise ValueError("Candidate ELO requires a finite observed overall rating")
    surface_counts = (rating.hard_matches, rating.clay_matches, rating.grass_matches)
    counts = (rating.overall_matches, *surface_counts)
    if any(type(n) is not int or n < 0 for n in counts) or sum(surface_counts) > rating.overall_matches:
        raise ValueError("Candidate ELO match counts are inconsistent")
    for value, count in zip((rating.hard, rating.clay, rating.grass), surface_counts):
        if (value is None) != (count == 0) or (value is not None and not math.isfinite(value)):
            raise ValueError("Candidate ELO surface ratings must agree with their observed counts")


def _params(snapshot: TennisEloSnapshot) -> dict[str, object]:
    return {
        "player_id": snapshot.player_id, "source": snapshot.source, "as_of_date": snapshot.as_of_date,
        "overall": snapshot.rating.overall, "hard": snapshot.rating.hard,
        "clay": snapshot.rating.clay, "grass": snapshot.rating.grass,
        "overall_matches": snapshot.rating.overall_matches, "hard_matches": snapshot.rating.hard_matches,
        "clay_matches": snapshot.rating.clay_matches, "grass_matches": snapshot.rating.grass_matches,
        "provider_namespace": snapshot.provider_namespace, "provider_player_id": snapshot.provider_player_id,
        "computed_at": snapshot.computed_at, "source_downloaded_at": snapshot.source_downloaded_at,
        "replay_cutoff": snapshot.replay_cutoff, "method_version": snapshot.method_version,
        "manifest_sha256": snapshot.manifest_sha256,
    }


def _from_row(row: RowMapping) -> TennisEloSnapshot:
    return TennisEloSnapshot(
        player_id=row["player_id"], source=row["source"], as_of_date=row["as_of_date"],
        rating=TennisEloRating(*(row[col] for col in _COLUMNS[3:11])),
        provider_namespace=row["provider_namespace"], provider_player_id=row["provider_player_id"],
        computed_at=row["computed_at"], source_downloaded_at=row["source_downloaded_at"],
        replay_cutoff=row["replay_cutoff"], method_version=row["method_version"],
        manifest_sha256=row["manifest_sha256"],
    )


async def get_daily_snapshots(
    db: AsyncSession, *, source: str, as_of_date: date,
) -> list[TennisEloSnapshot]:
    if source != SOURCE:
        raise ValueError("Explicit candidate ELO v1 source required")
    rows = (await db.execute(text(f"""
        SELECT {', '.join(_COLUMNS)} FROM tennis_elo_snapshots
        WHERE source = :source AND as_of_date = :as_of_date
        ORDER BY player_id
    """), {"source": source, "as_of_date": as_of_date})).mappings().all()
    return [_from_row(row) for row in rows]


def _validate_batch(snapshots: Sequence[TennisEloSnapshot]) -> None:
    provenance = {
        (s.source, s.as_of_date, s.computed_at, s.source_downloaded_at,
         s.replay_cutoff, s.method_version, s.manifest_sha256) for s in snapshots
    }
    players = {s.player_id for s in snapshots}
    providers = {(s.provider_namespace, s.provider_player_id) for s in snapshots}
    if len(provenance) != 1 or len(players) != len(snapshots) or len(providers) != len(snapshots):
        raise ValueError("Candidate ELO batch requires one provenance and unique player/provider mappings")


async def insert_daily_snapshots(db: AsyncSession, snapshots: Sequence[TennisEloSnapshot]) -> int:
    """Insert a complete day atomically; identical retries return zero, revisions fail."""
    if not snapshots:
        return 0
    _validate_batch(snapshots)
    first = snapshots[0]
    lock_key = f"tennis_elo_snapshots|{first.source}|{first.as_of_date.isoformat()}"
    lock_id = int.from_bytes(hashlib.sha256(lock_key.encode()).digest()[:8], signed=True)
    async with db.begin_nested():
        await db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
        existing = await get_daily_snapshots(db, source=first.source, as_of_date=first.as_of_date)
        if existing:
            if {s.player_id: s for s in existing} != {s.player_id: s for s in snapshots}:
                raise ValueError("Candidate ELO daily snapshot is already frozen with different facts or provenance")
            return 0
        await db.execute(text(f"""
            INSERT INTO tennis_elo_snapshots ({', '.join(_COLUMNS)})
            VALUES ({', '.join(':' + col for col in _COLUMNS)})
        """), [_params(s) for s in snapshots])
    return len(snapshots)
