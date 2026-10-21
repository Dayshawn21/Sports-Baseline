"""Build shadow pairs from the serving batch without writing served predictions."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import re

from app.core.odds import STALE_ODDS_HOURS, odds_are_stale
from app.core.tennis_elo import TennisEloMatch
from app.core.tennis_format import is_qualifying_event, is_qualifying_round
from app.core.tennis_market_blend_fit import FIT_COEFFICIENTS
from app.ml.registry import ModelRegistry
from app.repositories.matches import Match
from app.repositories.players import normalize_name
from app.repositories.tennis_elo import TennisEloSnapshot
from app.repositories.tennis_elo_comparison import (
    EXPERIMENT, ComparisonGroup, CoverageAttempt, FreezeCycle, FrozenComparison, FrozenForecast,
    FrozenIncumbentRating, FrozenMarket,
)
from app.services.tennis.ensemble import (
    ELO_MAX_MARKET_GAP, ELO_MIN_PRIOR_MATCHES, ENSEMBLE_VERSION, EnsembleInput, blend, elo_is_unreliable,
)
from app.services.tennis.feature_builder import SURFACE_MAP
from app.services.tennis.predictor import PredictionBatch, PredictionOutput, _elo_probability

SPEC_APPROVED_ON = date(2026, 10, 20)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def runtime_pins(registry: ModelRegistry, identity_sha256: str) -> dict[str, object]:
    return {
        "experiment_version": EXPERIMENT,
        "identity_sha256": identity_sha256,
        "coefficient_sha256": _digest({g: asdict(c) for g, c in FIT_COEFFICIENTS.items()}),
        "gate_sha256": _digest({"max_market_gap": ELO_MAX_MARKET_GAP,
                                "min_prior_matches": ELO_MIN_PRIOR_MATCHES,
                                "stale_odds_hours": STALE_ODDS_HOURS, "high_overround": 0.08}),
        "model_versions": {tour: f"{ENSEMBLE_VERSION}+lgbm-{registry.get_lgbm_version(tour) or 'none'}"
                           for tour in ("ATP", "WTA", "CHALLENGER")},
    }


@dataclass(frozen=True)
class ExperimentConfig:
    identity_sha256: str
    coefficient_sha256: str
    gate_sha256: str
    model_versions: tuple[tuple[str, str], ...]
    activated_at: datetime | None

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> ExperimentConfig:
        if record.get("experiment_version") != EXPERIMENT:
            raise ValueError("Explicit ELO source experiment version required")
        models = record.get("model_versions")
        if not isinstance(models, dict) or set(models) != {"ATP", "WTA", "CHALLENGER"}:
            raise ValueError("Experiment must pin all three incumbent model versions")
        activated = record.get("activated_at")
        result = cls(str(record["identity_sha256"]), str(record["coefficient_sha256"]),
                     str(record["gate_sha256"]), tuple(sorted((str(k), str(v)) for k, v in models.items())),
                     datetime.fromisoformat(str(activated)) if activated is not None else None)
        if any(not re.fullmatch(r"[a-f0-9]{64}", v) for v in (
            result.identity_sha256, result.coefficient_sha256, result.gate_sha256,
        )) or any(not v.strip() for _, v in result.model_versions):
            raise ValueError("Experiment requires SHA-256 pins and named incumbent versions")
        if result.activated_at is not None and result.activated_at.utcoffset() is None:
            raise ValueError("Experiment activation must be timezone-aware")
        return result

    @property
    def eligible_from(self) -> date | None:
        if self.activated_at is None:
            return None
        return max(SPEC_APPROVED_ON, self.activated_at.astimezone(timezone.utc).date()) + timedelta(days=1)

    def pins(self) -> dict[str, object]:
        return {"experiment_version": EXPERIMENT, "identity_sha256": self.identity_sha256,
                "coefficient_sha256": self.coefficient_sha256, "gate_sha256": self.gate_sha256,
                "model_versions": dict(self.model_versions)}

    @property
    def sha256(self) -> str:
        activated = self.activated_at.astimezone(timezone.utc).isoformat() if self.activated_at else None
        return _digest({**self.pins(), "activated_at": activated,
                        "spec_approved_on": SPEC_APPROVED_ON.isoformat()})

    def check_runtime(self, registry: ModelRegistry, identity_sha256: str) -> None:
        if self.pins() != runtime_pins(registry, identity_sha256):
            raise ValueError("Pinned ELO experiment inputs changed; accrual stopped for review")


@dataclass(frozen=True)
class ComparisonPlan:
    cycle: FreezeCycle
    pairs: tuple[FrozenComparison, ...]
    preview_pairs: int
    experiment_active: bool


def _group(match: Match, batch: PredictionBatch) -> ComparisonGroup | None:
    players = [batch.players.get(pid) for pid in (match.p1_id, match.p2_id)]
    if any(p is None for p in players):
        return None
    tours = {p.tour for p in players}
    if match.tour == "WTA" and tours == {"WTA"}:
        return "WTA"
    if match.tour in {"ATP", "CHALLENGER"} and tours <= {"ATP", "CHALLENGER"}:
        return "ATP" if match.tour == "ATP" else "ATP_CHALLENGER"
    return None


def _base_exclusion(match: Match, batch: PredictionBatch, now: datetime, resulted: set[int]) -> str | None:
    if match.id in resulted or match.winner_id is not None or match.status != "scheduled":
        return "not_unstarted"
    if match.start_utc is None or match.start_utc.utcoffset() is None:
        return "unknown_kickoff"
    if match.start_utc <= now:
        return "already_started"
    if match.p1_id == match.p2_id or _group(match, batch) is None:
        return "ambiguous_players_or_group"
    if is_qualifying_round(match.round) or is_qualifying_event(match.tournament):
        return "qualifying"
    if re.search(r"exhib|\bitf\b|\bdoubles\b", match.tournament or "", flags=re.I):
        return "outside_population"
    market = batch.odds.get(match.id)
    if not market or not market.get("row_id") or not market.get("p1_odds") or not market.get("p2_odds"):
        return "missing_market"
    fetched = market.get("fetched_at")
    if fetched is None or fetched.utcoffset() is None or fetched > now:
        return "unavailable_market"
    if odds_are_stale(fetched, now=now):
        return "stale_market"
    ratings = [batch.elo.get(pid) for pid in (match.p1_id, match.p2_id)]
    if any(r is None or not r.elo or r.as_of_date > now.date() or any(
        v is not None and not math.isfinite(v) for v in (r.elo, r.elo_hard, r.elo_clay, r.elo_grass)
    ) for r in ratings):
        return "missing_incumbent"
    if min(batch.prior_counts(match)) < ELO_MIN_PRIOR_MATCHES:
        return "insufficient_incumbent_history"
    return None


def source_result_targets(
    matches: list[Match], results: list[TennisEloMatch], candidates: Mapping[int, TennisEloSnapshot],
) -> set[int]:
    """Reject a target identifiable among completed inputs, even if the local status lags."""
    by_pair: dict[tuple[str, tuple[str, ...], str], list[TennisEloMatch]] = {}
    for result in results:
        key = (result.namespace, tuple(sorted((result.winner_id, result.loser_id))), result.round)
        by_pair.setdefault(key, []).append(result)
    found = set()
    for match in matches:
        if match.p1_id not in candidates or match.p2_id not in candidates:
            continue
        a, b = candidates[match.p1_id], candidates[match.p2_id]
        key = (a.provider_namespace, tuple(sorted((a.provider_player_id, b.provider_player_id))), match.round)
        event = normalize_name(match.tournament or "")
        for result in by_pair.get(key, []):
            source_event = normalize_name(result.tournament)
            if (0 <= (match.match_date - result.provider_date).days <= 14 and event and source_event
                    and (event in source_event or source_event in event)):
                found.add(match.id)
    return found


def _forecast(output: PredictionOutput, prior: int) -> FrozenForecast:
    return FrozenForecast(output.p1_elo_prob, output.p1_win_prob,
                          tuple(sorted(output.ensemble_weights.items())), tuple(output.quality_flags),
                          elo_is_unreliable(output.p1_elo_prob, output.p1_market_prob, prior))


def _make_pair(
    match: Match, batch: PredictionBatch, candidates: Mapping[int, TennisEloSnapshot],
    config: ExperimentConfig, now: datetime, baseline: PredictionOutput, *, preview: bool = False,
) -> FrozenComparison:
    c1, c2 = (candidates[pid] for pid in (match.p1_id, match.p2_id))
    surface = SURFACE_MAP.get(match.surface or "")
    s1, s2 = (getattr(c.rating, surface) if surface else None for c in (c1, c2))
    candidate_elo = _elo_probability({"has_surface_elo": s1 is not None and s2 is not None,
                                      "d_surface_elo": s1 - s2 if s1 is not None and s2 is not None else None,
                                      "d_elo": c1.rating.overall - c2.rating.overall})
    unreliable = elo_is_unreliable(candidate_elo, baseline.p1_market_prob,
                                   min(c1.rating.overall_matches, c2.rating.overall_matches))
    result = blend(EnsembleInput(
        tour=match.tour, elo_prob=candidate_elo, ml_prob=baseline.p1_ml_prob,
        market_prob=baseline.p1_market_prob, elo_unreliable=unreliable,
        ml_features_partial="ml_features_partial" in baseline.quality_flags,
        market_stale="stale_odds" in baseline.quality_flags,
        market_high_overround="high_overround" in baseline.quality_flags,
    ))
    common_flags = set(baseline.quality_flags) - {"elo_unreliable", "elo_fallback_used", "elo_missing"}
    candidate = FrozenForecast(candidate_elo, result.p1_win_prob, tuple(sorted(result.weights.items())),
                               tuple(sorted(common_flags | set(result.quality_flags))), unreliable)
    market = batch.odds[match.id]
    counts = batch.prior_counts(match)
    incumbent = tuple(FrozenIncumbentRating(
        pid, batch.elo[pid].as_of_date, batch.elo[pid].elo, batch.elo[pid].elo_hard,
        batch.elo[pid].elo_clay, batch.elo[pid].elo_grass, counts[i],
    ) for i, pid in enumerate((match.p1_id, match.p2_id)))
    return FrozenComparison(
        match.id, match.p1_id, match.p2_id, _group(match, batch), match.surface, match.start_utc, now,
        dict(config.model_versions)[match.tour], config.coefficient_sha256, config.gate_sha256,
        config.identity_sha256, FrozenMarket(match.id, market["row_id"], market["book"], market["fetched_at"],
                                             market["p1_odds"], market["p2_odds"], baseline.p1_market_prob),
        incumbent, (c1, c2), _forecast(baseline, min(counts)), candidate, baseline.p1_ml_prob,
        config.sha256, None if preview else config.activated_at, None if preview else config.eligible_from,
    )


def build_plan(
    matches: list[Match], batch: PredictionBatch, registry: ModelRegistry,
    candidates: Mapping[int, TennisEloSnapshot], config: ExperimentConfig, *,
    now: datetime, cycle_key: datetime, resulted: set[int], frozen: set[int],
    snapshot_error: str | None = None,
) -> ComparisonPlan:
    """Preview readiness while inactive; only active, mature-start cohorts produce storable pairs."""
    if now.utcoffset() is None:
        raise ValueError("Freeze clock must be timezone-aware")
    now = now.astimezone(timezone.utc)
    active = config.eligible_from is not None and now.date() >= config.eligible_from
    attempts, pairs, preview_pairs = [], [], 0
    for match in matches:
        group = _group(match, batch)
        reason = _base_exclusion(match, batch, now, resulted)
        eligible, available = reason is None, False
        if eligible and match.id in frozen:
            reason = "already_frozen"
        if eligible and config.eligible_from and match.start_utc.date() < config.eligible_from:
            eligible, reason = False, "before_experiment_start"
        if reason is None:
            baseline = batch.build(registry, match, now=now)
            try:
                if snapshot_error:
                    raise ValueError(snapshot_error)
                if any(pid not in candidates for pid in (match.p1_id, match.p2_id)):
                    raise ValueError("missing_candidate")
                value = _make_pair(match, batch, candidates, config, now, baseline, preview=not active)
                available = True
            except ValueError:
                reason = snapshot_error or "missing_or_invalid_candidate"
            else:
                preview_pairs += 1
                if active:
                    pairs.append(value)
                    reason = "paired"
                else:
                    reason = "experiment_inactive"
        kickoff = match.start_utc if match.start_utc and match.start_utc.utcoffset() is not None else None
        attempts.append(CoverageAttempt(match.id, group, kickoff, eligible, available, reason, config.sha256))
    return ComparisonPlan(FreezeCycle(cycle_key, now, tuple(attempts)), tuple(pairs), preview_pairs, active)
