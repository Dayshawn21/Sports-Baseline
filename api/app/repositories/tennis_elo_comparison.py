"""Atomic shadow-only forecast freezes and immutable coverage ledgers."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timezone
import hashlib
import json
import math
import re
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.odds import american_to_prob, devig_two_way, odds_are_stale
from app.repositories.tennis_elo import TennisEloSnapshot

EXPERIMENT = "tennis-elo-source-v1"
ComparisonGroup = Literal["ATP", "WTA", "ATP_CHALLENGER"]
_GROUPS = {"ATP", "WTA", "ATP_CHALLENGER"}


def _aware(value: datetime) -> None:
    if value.utcoffset() is None:
        raise ValueError("Comparison timestamps must be timezone-aware")


def _probability(value: float) -> None:
    if not math.isfinite(value) or not 0 < value < 1:
        raise ValueError("Comparison probabilities must be finite and strictly between zero and one")


def _positive_id(value: int) -> None:
    if type(value) is not int or value < 1:
        raise ValueError("Comparison identifiers must be positive integers")


@dataclass(frozen=True)
class FrozenMarket:
    match_id: int
    row_id: int
    book: str
    fetched_at: datetime
    p1_odds: int
    p2_odds: int
    p1_probability: float

    def __post_init__(self) -> None:
        _positive_id(self.match_id)
        _positive_id(self.row_id)
        _aware(self.fetched_at)
        _probability(self.p1_probability)
        if not self.book.strip() or any(type(v) is not int or v == 0 for v in (self.p1_odds, self.p2_odds)):
            raise ValueError("A frozen market needs a book and two nonzero American odds")
        expected, _ = devig_two_way(american_to_prob(self.p1_odds), american_to_prob(self.p2_odds))
        if not math.isclose(expected, self.p1_probability, rel_tol=0, abs_tol=1e-12):
            raise ValueError("Frozen market probability disagrees with its oriented odds")


@dataclass(frozen=True)
class FrozenIncumbentRating:
    player_id: int
    as_of_date: date
    overall: float
    hard: float | None
    clay: float | None
    grass: float | None
    prior_matches: int

    def __post_init__(self) -> None:
        _positive_id(self.player_id)
        if type(self.prior_matches) is not int or self.prior_matches < 10:
            raise ValueError("A paired incumbent requires at least ten prior matches per player")
        if not math.isfinite(self.overall) or any(
            value is not None and not math.isfinite(value) for value in (self.hard, self.clay, self.grass)
        ):
            raise ValueError("Incumbent ratings must be finite")


@dataclass(frozen=True)
class FrozenForecast:
    elo_probability: float
    win_probability: float
    weights: tuple[tuple[str, float], ...]
    quality_flags: tuple[str, ...]
    elo_unreliable: bool

    def __post_init__(self) -> None:
        _probability(self.elo_probability)
        _probability(self.win_probability)
        if not isinstance(self.weights, tuple) or not isinstance(self.quality_flags, tuple):
            raise ValueError("Forecast weights and flags must be immutable tuples")
        if (not self.weights or any(not isinstance(w, tuple) or len(w) != 2 for w in self.weights)
                or len({name for name, _ in self.weights}) != len(self.weights)
                or any(not name or not math.isfinite(value) for name, value in self.weights)):
            raise ValueError("Invalid frozen ensemble weights")
        if any(not isinstance(flag, str) or not flag for flag in self.quality_flags):
            raise ValueError("Invalid frozen quality flags")
        if type(self.elo_unreliable) is not bool:
            raise ValueError("Frozen ELO reliability must be explicit")


@dataclass(frozen=True)
class FrozenComparison:
    match_id: int
    p1_id: int
    p2_id: int
    group: ComparisonGroup
    surface: str | None
    kickoff: datetime
    frozen_at: datetime
    incumbent_model_version: str
    coefficient_sha256: str
    gate_sha256: str
    identity_sha256: str
    market: FrozenMarket
    incumbent_ratings: tuple[FrozenIncumbentRating, FrozenIncumbentRating]
    candidate_ratings: tuple[TennisEloSnapshot, TennisEloSnapshot]
    incumbent: FrozenForecast
    candidate: FrozenForecast
    ml_probability: float | None
    experiment_sha256: str
    activated_at: datetime | None
    eligible_from: date | None

    def __post_init__(self) -> None:
        for value in (self.match_id, self.p1_id, self.p2_id):
            _positive_id(value)
        _aware(self.kickoff)
        _aware(self.frozen_at)
        if self.group not in _GROUPS or self.p1_id == self.p2_id or self.market.match_id != self.match_id:
            raise ValueError("Comparison group, players or market orientation is inconsistent")
        if not self.incumbent_model_version.strip() or any(not re.fullmatch(r"[a-f0-9]{64}", v) for v in (
            self.coefficient_sha256, self.gate_sha256, self.identity_sha256, self.experiment_sha256,
        )):
            raise ValueError("Comparison requires pinned model, coefficients, gates and identity provenance")
        if self.ml_probability is not None:
            _probability(self.ml_probability)
        self._validate_inputs()

    def _validate_inputs(self) -> None:
        day = self.frozen_at.astimezone(timezone.utc).date()
        if (self.activated_at is None) != (self.eligible_from is None):
            raise ValueError("Activation and first eligible day must be pinned together")
        if self.activated_at is not None:
            _aware(self.activated_at)
            if (self.eligible_from <= self.activated_at.astimezone(timezone.utc).date()
                    or day < self.eligible_from or self.kickoff.astimezone(timezone.utc).date() < self.eligible_from):
                raise ValueError("Comparison must belong to a full UTC day after experiment activation")
        if (not self.frozen_at < self.kickoff or self.market.fetched_at > self.frozen_at
                or odds_are_stale(self.market.fetched_at, now=self.frozen_at)):
            raise ValueError("Comparison must precede kickoff and use an available fresh market")
        players = (self.p1_id, self.p2_id)
        for ratings in (self.incumbent_ratings, self.candidate_ratings):
            if not isinstance(ratings, tuple) or tuple(r.player_id for r in ratings) != players:
                raise ValueError("Comparison rating orientation must equal p1 then p2")
        if any(r.as_of_date > day for r in self.incumbent_ratings):
            raise ValueError("Incumbent ratings cannot come from a future date")
        namespace = "WTA" if self.group == "WTA" else "ATP"
        for rating in self.candidate_ratings:
            if (rating.as_of_date != day or rating.computed_at > self.frozen_at
                    or rating.provider_namespace != namespace or rating.rating.overall_matches < 10):
                raise ValueError("Candidate needs current-day pre-freeze ratings, correct namespace and ten matches")
        a, b = self.candidate_ratings
        if (a.manifest_sha256, a.computed_at, a.source_downloaded_at) != (
            b.manifest_sha256, b.computed_at, b.source_downloaded_at
        ):
            raise ValueError("Candidate players must use the same complete daily snapshot")
        if a.provider_player_id == b.provider_player_id:
            raise ValueError("Candidate provider identities must be distinct")


@dataclass(frozen=True)
class CoverageAttempt:
    match_id: int
    group: ComparisonGroup | None
    kickoff: datetime | None
    incumbent_eligible: bool
    candidate_available: bool
    reason: str
    experiment_sha256: str | None = None

    def __post_init__(self) -> None:
        _positive_id(self.match_id)
        if self.experiment_sha256 is not None and not re.fullmatch(r"[a-f0-9]{64}", self.experiment_sha256):
            raise ValueError("Coverage experiment pin must be a SHA-256 hash")
        if self.group is not None and self.group not in _GROUPS:
            raise ValueError("Unknown coverage group")
        if self.kickoff is not None:
            _aware(self.kickoff)
        if (type(self.incumbent_eligible) is not bool or type(self.candidate_available) is not bool
                or not re.fullmatch(r"[a-z][a-z0-9_]*", self.reason)):
            raise ValueError("Coverage needs explicit eligibility and a reason code")
        if self.incumbent_eligible and (self.group is None or self.kickoff is None):
            raise ValueError("Eligible coverage requires a group and scheduled kickoff")
        if self.reason == "paired" and not (self.incumbent_eligible and self.candidate_available):
            raise ValueError("A paired attempt needs both eligible sources")


@dataclass(frozen=True)
class FreezeCycle:
    cycle_key: datetime
    frozen_at: datetime
    attempts: tuple[CoverageAttempt, ...]

    def __post_init__(self) -> None:
        _aware(self.cycle_key)
        _aware(self.frozen_at)
        if self.cycle_key > self.frozen_at:
            raise ValueError("Freeze cycle key cannot be after its observation time")
        if not isinstance(self.attempts, tuple) or len({a.match_id for a in self.attempts}) != len(self.attempts):
            raise ValueError("Coverage attempts must be an immutable unique match roster")
        if any(a.incumbent_eligible and a.kickoff <= self.frozen_at for a in self.attempts):
            raise ValueError("Eligible coverage cannot include already-started matches")


def _json(value: object) -> str:
    def encode(item: object) -> str:
        if isinstance(item, datetime):
            return item.astimezone(timezone.utc).isoformat()
        if isinstance(item, date):
            return item.isoformat()
        raise TypeError(f"Unsupported frozen payload type: {type(item).__name__}")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=encode, allow_nan=False)


def _validate_cycle(cycle: FreezeCycle, pairs: Sequence[FrozenComparison]) -> str:
    paired = {a.match_id: a for a in cycle.attempts if a.reason == "paired"}
    if {p.match_id for p in pairs} != set(paired) or len(pairs) != len(paired):
        raise ValueError("Every paired coverage attempt needs exactly one comparison")
    for pair in pairs:
        attempt = paired[pair.match_id]
        if pair.frozen_at != cycle.frozen_at or (pair.group, pair.kickoff) != (attempt.group, attempt.kickoff):
            raise ValueError("Comparison and coverage cycle metadata disagree")
        if attempt.experiment_sha256 is not None and attempt.experiment_sha256 != pair.experiment_sha256:
            raise ValueError("Comparison and coverage experiment pins disagree")
    if len({a.experiment_sha256 for a in cycle.attempts if a.experiment_sha256 is not None}) > 1:
        raise ValueError("Coverage attempts must share one experiment pin")
    versions = {
        (p.coefficient_sha256, p.gate_sha256, p.identity_sha256,
         p.candidate_ratings[0].manifest_sha256, p.experiment_sha256, p.activated_at, p.eligible_from) for p in pairs
    }
    if len(versions) > 1:
        raise ValueError("A comparison cycle requires one pinned experiment and candidate snapshot")
    for group in _GROUPS:
        if len({p.incumbent_model_version for p in pairs if p.group == group}) > 1:
            raise ValueError("A comparison group requires one incumbent model version")
    plan = {
        "experiment_version": EXPERIMENT, "cycle_key": cycle.cycle_key, "frozen_at": cycle.frozen_at,
        "attempts": [asdict(a) for a in sorted(cycle.attempts, key=lambda a: a.match_id)],
        "pairs": [asdict(p) for p in sorted(pairs, key=lambda p: p.match_id)],
    }
    return hashlib.sha256(_json(plan).encode()).hexdigest()


async def get_frozen_match_ids(db: AsyncSession) -> set[int]:
    rows = await db.execute(text(
        "SELECT match_id FROM tennis_elo_comparisons WHERE experiment_version = :experiment"
    ), {"experiment": EXPERIMENT})
    return set(rows.scalars())


async def get_cycle_attempt_count(db: AsyncSession, cycle_key: datetime) -> int | None:
    return (await db.execute(text(
        "SELECT jsonb_array_length(attempts) FROM tennis_elo_freeze_cycles "
        "WHERE experiment_version = :experiment AND cycle_key = :cycle_key"
    ), {"experiment": EXPERIMENT, "cycle_key": cycle_key})).scalar_one_or_none()


async def check_experiment_continuity(db: AsyncSession, experiment_sha256: str) -> None:
    hashes = set((await db.execute(text(
        "SELECT DISTINCT payload->>'experiment_sha256' FROM tennis_elo_comparisons "
        "WHERE experiment_version = :experiment UNION "
        "SELECT DISTINCT attempt->>'experiment_sha256' FROM tennis_elo_freeze_cycles, "
        "jsonb_array_elements(attempts) AS attempt WHERE experiment_version = :experiment "
        "AND attempt->>'experiment_sha256' IS NOT NULL"
    ), {"experiment": EXPERIMENT})).scalars())
    if hashes - {experiment_sha256}:
        raise ValueError("Experiment configuration changed after a frozen comparison; review required")


async def get_resulted_match_ids(db: AsyncSession, match_ids: list[int]) -> set[int]:
    rows = await db.execute(text(
        "SELECT id FROM matches WHERE id = ANY(:ids) AND "
        "(winner_id IS NOT NULL OR (score IS NOT NULL AND btrim(score) <> ''))"
    ), {"ids": match_ids})
    return set(rows.scalars())


async def _insert_pair(db: AsyncSession, cycle: FreezeCycle, pair: FrozenComparison) -> int:
    unchanged_match = (await db.execute(text(
        "SELECT id FROM matches WHERE id = :match_id AND p1_id = :p1_id AND p2_id = :p2_id "
        "AND start_utc = :kickoff AND status = 'scheduled' AND winner_id IS NULL "
        "AND (score IS NULL OR btrim(score) = '') FOR SHARE"
    ), {"match_id": pair.match_id, "p1_id": pair.p1_id, "p2_id": pair.p2_id,
        "kickoff": pair.kickoff})).scalar_one_or_none()
    if unchanged_match is None:
        raise ValueError("Match changed orientation, kickoff or unstarted status before freeze")
    result = await db.execute(text(
        "INSERT INTO tennis_elo_comparisons "
        "(match_id, experiment_version, cycle_key, p1_id, p2_id, comparison_group, kickoff, frozen_at, payload) "
        "SELECT :match_id, :experiment, :cycle_key, :p1_id, :p2_id, :group, :kickoff, :frozen_at, "
        "CAST(:payload AS jsonb) WHERE clock_timestamp() < :kickoff "
        "ON CONFLICT (match_id, experiment_version) DO NOTHING RETURNING match_id"
    ), {"experiment": EXPERIMENT, "cycle_key": cycle.cycle_key,
        "match_id": pair.match_id, "p1_id": pair.p1_id, "p2_id": pair.p2_id,
        "group": pair.group, "kickoff": pair.kickoff, "frozen_at": pair.frozen_at,
        "payload": _json(asdict(pair))})
    if result.scalar_one_or_none() is None:
        raise ValueError("Comparison insert did not precede kickoff or its key already exists")
    return 1


async def freeze_cycle(db: AsyncSession, cycle: FreezeCycle, pairs: Sequence[FrozenComparison]) -> int:
    """Freeze the whole ledger and new pairs atomically; never replace an earlier pair.

    The caller commits. Same-cycle changes fail; a later cycle can observe a match
    again, but its first comparison remains authoritative for this experiment.
    """
    pairs = tuple(pairs)
    if any(p.activated_at is None for p in pairs):
        raise ValueError("Inactive experiment previews cannot be persisted")
    plan_hash = _validate_cycle(cycle, pairs)
    key = {"experiment": EXPERIMENT, "cycle_key": cycle.cycle_key}
    lock_id = int.from_bytes(hashlib.sha256(EXPERIMENT.encode()).digest()[:8], signed=True)
    async with db.begin_nested():
        await db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
        existing = (await db.execute(text(
            "SELECT plan_sha256 FROM tennis_elo_freeze_cycles "
            "WHERE experiment_version = :experiment AND cycle_key = :cycle_key"
        ), key)).scalar_one_or_none()
        if existing is not None:
            if existing != plan_hash:
                raise ValueError("Comparison cycle is already frozen with different facts")
            return 0
        pins = {a.experiment_sha256 for a in cycle.attempts if a.experiment_sha256 is not None}
        if pairs or pins:
            await check_experiment_continuity(db, pairs[0].experiment_sha256 if pairs else next(iter(pins)))
        now = (await db.execute(text("SELECT clock_timestamp()"))).scalar_one()
        if cycle.frozen_at > now or any(a.incumbent_eligible and a.kickoff <= now for a in cycle.attempts):
            raise ValueError("Comparison cannot be persisted in the future or after kickoff")
        existing_ids = await get_frozen_match_ids(db) if pairs else set()
        attempts = tuple(replace(a, reason="already_frozen")
                         if a.reason == "paired" and a.match_id in existing_ids else a for a in cycle.attempts)
        await db.execute(text(
            "INSERT INTO tennis_elo_freeze_cycles "
            "(experiment_version, cycle_key, frozen_at, plan_sha256, attempts) "
            "VALUES (:experiment, :cycle_key, :frozen_at, :plan_sha256, CAST(:attempts AS jsonb))"
        ), {**key, "frozen_at": cycle.frozen_at, "plan_sha256": plan_hash,
            "attempts": _json([asdict(a) for a in sorted(attempts, key=lambda a: a.match_id)])})
        inserted = 0
        for pair in pairs:
            if pair.match_id not in existing_ids:
                inserted += await _insert_pair(db, cycle, pair)
    return inserted
