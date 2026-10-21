"""Separate outcome-free report reads from explicitly requested result reads."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tennis_elo import TennisEloRating
from app.core.tennis_elo_report import (
    CoverageObservation, MatchState, Probabilities, ReportCase, ResultObservation,
)
from app.repositories.tennis_elo import TennisEloSnapshot
from app.repositories.tennis_elo_comparison import (
    EXPERIMENT, CoverageAttempt, FreezeCycle, FrozenComparison, FrozenForecast, FrozenIncumbentRating,
    FrozenMarket,
)


def _record(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError("Frozen payload must be an object")
    return cast(dict[str, object], value)


def _array(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("Frozen payload must contain an array")
    return cast(list[object], value)


def _dates(value: object, days: tuple[str, ...] = (), times: tuple[str, ...] = ()) -> dict[str, object]:
    record = dict(_record(value))
    for key in days:
        record[key] = date.fromisoformat(str(record[key])) if record[key] is not None else None
    for key in times:
        record[key] = datetime.fromisoformat(str(record[key])) if record[key] is not None else None
    return record


def decode_comparison(value: object) -> FrozenComparison:
    record = _dates(value, ("eligible_from",), ("kickoff", "frozen_at", "activated_at"))
    record["market"] = FrozenMarket(**_dates(record["market"], times=("fetched_at",)))
    incumbent, candidate = [], []
    for item in _array(record["incumbent_ratings"]):
        incumbent.append(FrozenIncumbentRating(**_dates(item, ("as_of_date",))))
    for item in _array(record["candidate_ratings"]):
        rating = _dates(item, ("as_of_date", "replay_cutoff"), ("computed_at", "source_downloaded_at"))
        rating["rating"] = TennisEloRating(**_record(rating["rating"]))
        candidate.append(TennisEloSnapshot(**rating))
    record["incumbent_ratings"], record["candidate_ratings"] = tuple(incumbent), tuple(candidate)
    for name in ("incumbent", "candidate"):
        forecast = dict(_record(record[name]))
        forecast["weights"] = tuple(tuple(_array(w)) for w in _array(forecast["weights"]))
        forecast["quality_flags"] = tuple(_array(forecast["quality_flags"]))
        record[name] = FrozenForecast(**forecast)
    return FrozenComparison(**record)


def _report_case(comparison: FrozenComparison, current: MatchState, probabilities: bool) -> ReportCase:
    c = comparison
    values = Probabilities(c.candidate.win_probability, c.incumbent.win_probability, c.market.p1_probability,
                           c.candidate.elo_probability, c.incumbent.elo_probability) if probabilities else None
    return ReportCase(
        c.match_id, c.p1_id, c.p2_id, c.group, EXPERIMENT, c.experiment_sha256, c.incumbent_model_version,
        c.coefficient_sha256, c.gate_sha256, c.identity_sha256, c.candidate_ratings[0].source,
        c.frozen_at, c.kickoff, c.eligible_from, current, c.surface,
        c.candidate.elo_unreliable, c.incumbent.elo_unreliable, values,
    )


@dataclass(frozen=True)
class ReportInputs:
    cases: tuple[ReportCase, ...]
    coverage: tuple[CoverageObservation, ...]
    invalid_payloads: int


async def begin_read_only_report(db: AsyncSession) -> None:
    """Keep all report reads in one consistent, database-enforced read-only view."""
    await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))


async def get_report_inputs(db: AsyncSession, *, include_probabilities: bool = False) -> ReportInputs:
    """No winner or score columns, and no grading loader, on this path."""
    rows = (await db.execute(text(
        "SELECT c.match_id,c.p1_id,c.p2_id,c.comparison_group,c.frozen_at,c.kickoff,c.payload,"
        "m.p1_id AS current_p1,m.p2_id AS current_p2,m.start_utc AS current_kickoff,"
        "m.status,m.tour,m.tournament,m.round,m.best_of "
        "FROM tennis_elo_comparisons c LEFT JOIN matches m ON m.id=c.match_id "
        "WHERE c.experiment_version=:experiment ORDER BY c.kickoff,c.match_id"
    ), {"experiment": EXPERIMENT})).mappings().all()
    cases, invalid = [], 0
    for row in rows:
        try:
            pair = decode_comparison(row["payload"])
            if (pair.match_id, pair.p1_id, pair.p2_id, pair.group, pair.frozen_at, pair.kickoff) != (
                row["match_id"], row["p1_id"], row["p2_id"], row["comparison_group"], row["frozen_at"], row["kickoff"],
            ):
                raise ValueError("Frozen columns disagree with copied payload")
            current = MatchState(row["current_p1"], row["current_p2"], row["current_kickoff"], row["status"],
                                 row["tour"], row["tournament"], row["round"], row["best_of"])
            cases.append(_report_case(pair, current, include_probabilities))
        except (ValueError, TypeError, KeyError, AttributeError):
            invalid += 1
    cycles = (await db.execute(text(
        "SELECT cycle_key,frozen_at,attempts FROM tennis_elo_freeze_cycles "
        "WHERE experiment_version=:experiment ORDER BY frozen_at,cycle_key"
    ), {"experiment": EXPERIMENT})).mappings().all()
    observations = []
    for row in cycles:
        attempts = tuple(CoverageAttempt(**_dates(item, times=("kickoff",))) for item in _array(row["attempts"]))
        cycle = FreezeCycle(row["cycle_key"], row["frozen_at"], attempts)
        observations.extend(CoverageObservation(a.match_id, a.group, a.kickoff, cycle.frozen_at,
                                                a.incumbent_eligible, a.candidate_available, a.reason,
                                                a.experiment_sha256) for a in attempts)
    return ReportInputs(tuple(cases), tuple(observations), invalid)


async def get_report_results(db: AsyncSession, match_ids: list[int]) -> dict[int, ResultObservation]:
    """Explicit score mode only; restrict results to the mature frozen candidate IDs."""
    if not match_ids:
        return {}
    rows = (await db.execute(text(
        "SELECT id,status,winner_id,score FROM matches WHERE id=ANY(:ids) ORDER BY id"
    ), {"ids": match_ids})).all()
    return {mid: ResultObservation(mid, status, winner, score) for mid, status, winner, score in rows}
