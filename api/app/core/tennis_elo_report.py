"""Pre-registered forward ELO source comparison; no I/O or model inference."""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from math import isfinite
import re

from app.core.tennis_format import infer_best_of, is_qualifying_event, is_qualifying_round
from app.core.tennis_grading import (
    CalibrationBin, ComponentScore, PairedDifference, calibration_bins, is_completed_score,
    paired_loss_difference, score_component,
)

EXPERIMENT = "tennis-elo-source-v1"
SOURCE = "tennismylife-elo-v1"
GROUPS = ("ATP", "WTA", "ATP_CHALLENGER")
MIN_CASES = 300
MIN_DAYS = 14
SETTLEMENT_DAYS = 3
STANDARD_ERRORS = 2.5
MARGIN = 0.005
MIN_COVERAGE_PERCENT = 90
RULE = {
    "rule_version": "tennis-elo-forward-v1", "experiment": EXPERIMENT, "source": SOURCE,
    "groups": GROUPS, "min_cases": MIN_CASES, "min_days": MIN_DAYS,
    "full_settlement_days": SETTLEMENT_DAYS, "standard_errors": STANDARD_ERRORS, "margin": MARGIN,
    "min_coverage_percent": MIN_COVERAGE_PERCENT, "sample": "first_fully_resolved_cohort_prefix",
    "coverage": "unique_incumbent_eligible_matches_in_frozen_cohorts_any_prestart_availability",
    "coverage_cohort": "successful_pair_cohort_else_first_eligible_attempt_no_outcome_filter",
    "start": "next_full_utc_day_after_spec_and_activation",
    "population": "main_draw_atp_wta_mens_challenger_no_itf_exhibition_doubles",
    "capture": "before_frozen_and_current_kickoffs_same_participants_and_pinned_versions",
    "settlement": "three_full_days_after_both_kickoff_cohort_days_close",
    "results": "completed_score_valid_winner_explicit_voids_excluded_other_unknowns_block_cohort",
}
RULE_SHA256 = hashlib.sha256(json.dumps(RULE, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class ReportPins:
    experiment_sha256: str
    eligible_from: date | None
    coefficient_sha256: str
    gate_sha256: str
    identity_sha256: str
    model_versions: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class MatchState:
    p1_id: int | None
    p2_id: int | None
    kickoff: datetime | None
    status: str | None
    tour: str | None
    tournament: str | None
    round: str | None
    best_of: int | None


@dataclass(frozen=True)
class Probabilities:
    candidate: float
    incumbent: float
    market: float
    candidate_elo: float
    incumbent_elo: float

    def __post_init__(self) -> None:
        if any(not isfinite(p) or not 0 < p < 1 for p in (
            self.candidate, self.incumbent, self.market, self.candidate_elo, self.incumbent_elo,
        )):
            raise ValueError("Locked probabilities must be finite and strictly between zero and one")


@dataclass(frozen=True)
class ReportCase:
    match_id: int
    p1_id: int
    p2_id: int
    group: str
    experiment: str
    experiment_sha256: str
    model_version: str
    coefficient_sha256: str
    gate_sha256: str
    identity_sha256: str
    candidate_source: str
    frozen_at: datetime
    kickoff: datetime
    eligible_from: date | None
    current: MatchState
    surface: str | None
    candidate_gated: bool
    incumbent_gated: bool
    probabilities: Probabilities | None


@dataclass(frozen=True)
class CoverageObservation:
    match_id: int
    group: str | None
    kickoff: datetime | None
    observed_at: datetime
    incumbent_eligible: bool
    candidate_available: bool
    reason: str
    experiment_sha256: str | None


@dataclass(frozen=True)
class ResultObservation:
    match_id: int
    status: str
    winner_id: int | None
    score: str | None


def utc_day(value: datetime) -> date:
    if value.utcoffset() is None:
        raise ValueError("Forward report timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).date()


def mature_through(now: datetime) -> date:
    # D's cohort closes at D+1 midnight; then wait three whole UTC days.
    return utc_day(now) - timedelta(days=SETTLEMENT_DAYS + 1)


def capture_exclusion(case: ReportCase, pins: ReportPins) -> str | None:
    if case.experiment != EXPERIMENT or case.candidate_source != SOURCE:
        return "other_source_or_experiment"
    if case.group not in GROUPS:
        return "outside_group"
    tour = "CHALLENGER" if case.group == "ATP_CHALLENGER" else case.group
    if (case.experiment_sha256 != pins.experiment_sha256
            or (case.coefficient_sha256, case.gate_sha256, case.identity_sha256) != (
                pins.coefficient_sha256, pins.gate_sha256, pins.identity_sha256)
            or case.model_version != dict(pins.model_versions)[tour]):
        raise ValueError("Frozen experiment versions changed; report stopped for review")
    if pins.eligible_from is None:
        return "experiment_inactive"
    if (case.eligible_from != pins.eligible_from or utc_day(case.kickoff) < pins.eligible_from
            or utc_day(case.frozen_at) < pins.eligible_from):
        return "before_start_or_wrong_cohort"
    if case.frozen_at >= case.kickoff:
        return "late_capture"
    current = case.current
    if case.p1_id == case.p2_id or {current.p1_id, current.p2_id} != {case.p1_id, case.p2_id}:
        return "participants_changed"
    if current.kickoff is None or current.kickoff.utcoffset() is None:
        return "current_kickoff_missing"
    if current.kickoff <= case.frozen_at:
        return "rescheduled_before_freeze"
    if (current.tour != tour or is_qualifying_round(current.round)
            or is_qualifying_event(current.tournament)
            or re.search(r"exhib|\bitf\b|\bdoubles\b", current.tournament or "", flags=re.I)):
        return "outside_population"
    return None


def valid_cases(cases: Sequence[ReportCase], pins: ReportPins) -> tuple[tuple[ReportCase, ...], dict[str, int]]:
    accepted, reasons, ids = [], Counter(), set()
    for case in sorted(cases, key=lambda c: (c.kickoff, c.match_id)):
        if case.match_id in ids:
            raise ValueError("Duplicate frozen match in one experiment")
        ids.add(case.match_id)
        reason = capture_exclusion(case, pins)
        if reason:
            reasons[reason] += 1
        else:
            accepted.append(case)
    return tuple(accepted), dict(reasons)


@dataclass(frozen=True)
class Coverage:
    eligible_ids: tuple[int, ...]
    available_ids: tuple[int, ...]

    @property
    def passes(self) -> bool:
        return bool(self.eligible_ids) and 100 * len(self.available_ids) >= MIN_COVERAGE_PERCENT * len(self.eligible_ids)


def coverage(
    observations: Sequence[CoverageObservation], cases: Sequence[ReportCase], pins: ReportPins,
    group: str, through: date,
) -> Coverage:
    by_match: dict[int, list[CoverageObservation]] = defaultdict(list)
    for row in observations:
        if row.group != group or not row.incumbent_eligible:
            continue
        if row.experiment_sha256 != pins.experiment_sha256:
            raise ValueError("Coverage experiment pin changed; report stopped for review")
        if (row.kickoff is None or row.observed_at >= row.kickoff
                or pins.eligible_from is None or utc_day(row.observed_at) < pins.eligible_from
                or utc_day(row.kickoff) < pins.eligible_from):
            raise ValueError("Invalid pre-match coverage observation")
        by_match[row.match_id].append(row)
    paired = {c.match_id: c for c in cases if c.group == group}
    eligible, available = [], []
    for mid, rows in by_match.items():
        case = paired.get(mid)
        chosen = case.kickoff if case else min(rows, key=lambda r: r.observed_at).kickoff
        same_cohort = [r for r in rows if r.kickoff == chosen]
        if not same_cohort:
            raise ValueError("Frozen comparison has no matching coverage cohort")
        if utc_day(chosen) > through:
            continue
        eligible.append(mid)
        if any(r.candidate_available for r in same_cohort):
            available.append(mid)
    return Coverage(tuple(sorted(eligible)), tuple(sorted(available)))


@dataclass(frozen=True)
class CountSummary:
    group: str
    frozen_pairs: int
    mature_pairs: int
    mature_kickoff_days: int
    eligible_attempts: int
    candidate_available: int
    potential_sample_floor: bool
    verdict: str = "accruing"


def count_summary(
    cases: Sequence[ReportCase], observations: Sequence[CoverageObservation], pins: ReportPins,
    group: str, now: datetime,
) -> CountSummary:
    subset = [c for c in cases if c.group == group]
    mature = [c for c in subset if utc_day(c.kickoff) <= mature_through(now)
              and c.current.kickoff is not None and utc_day(c.current.kickoff) <= mature_through(now)]
    days = len({utc_day(c.kickoff) for c in mature})
    cov = coverage(observations, cases, pins, group, mature_through(now))
    return CountSummary(group, len(subset), len(mature), days, len(cov.eligible_ids), len(cov.available_ids),
                        len(mature) >= MIN_CASES and days >= MIN_DAYS)


def resolve(case: ReportCase, result: ResultObservation | None) -> tuple[str, bool | None]:
    if result is None:
        return "unresolved", None
    if result.match_id != case.match_id:
        raise ValueError("Result observation does not match its frozen comparison")
    status = result.status.lower()
    if status in {"cancelled", "canceled", "void", "retired", "abandoned", "walkover"} or re.search(
        r"\b(?:ret|retired|walkover|abandoned|void|cancelled)\b|w\s*/\s*o", result.score or "", flags=re.I,
    ):
        return "void_or_retired", None
    if status != "completed" or result.winner_id not in (case.p1_id, case.p2_id):
        return "unresolved", None
    current = case.current
    best_of = infer_best_of(current.tour, current.tournament, current.round, current.best_of)
    if not is_completed_score(result.score, best_of):
        return "unresolved", None
    return "resolved", result.winner_id == case.p1_id


@dataclass(frozen=True)
class ScoredCase:
    match_id: int
    kickoff: datetime
    p1_won: bool
    probabilities: Probabilities
    surface: str | None
    candidate_gated: bool
    incumbent_gated: bool


@dataclass(frozen=True)
class SampleSelection:
    group: str
    cases: tuple[ScoredCase, ...]
    cutoff: date | None
    blocked_day: date | None
    excluded: tuple[tuple[str, int], ...]


def select_sample(
    cases: Sequence[ReportCase], results: Mapping[int, ResultObservation], group: str, now: datetime,
) -> SampleSelection:
    cohorts: dict[date, list[ReportCase]] = defaultdict(list)
    for case in cases:
        if case.group == group and utc_day(case.kickoff) <= mature_through(now):
            cohorts[utc_day(case.kickoff)].append(case)
    selected, excluded, days = [], Counter(), set()
    for day, members in sorted(cohorts.items()):
        resolved = [(c, *resolve(c, results.get(c.match_id)))
                    if c.current.kickoff is not None and utc_day(c.current.kickoff) <= mature_through(now)
                    else (c, "unresolved", None) for c in sorted(members, key=lambda c: c.match_id)]
        if any(state == "unresolved" for _, state, _ in resolved):
            return SampleSelection(group, tuple(selected), None, day, tuple(sorted(excluded.items())))
        for case, state, won in resolved:
            if state != "resolved":
                excluded[state] += 1
                continue
            if case.probabilities is None or type(won) is not bool:
                raise ValueError("Scoring requires copied probabilities and a resolved participant outcome")
            selected.append(ScoredCase(case.match_id, case.kickoff, won, case.probabilities, case.surface,
                                       case.candidate_gated, case.incumbent_gated))
            days.add(day)
        if len(selected) >= MIN_CASES and len(days) >= MIN_DAYS:
            return SampleSelection(group, tuple(selected), day, None, tuple(sorted(excluded.items())))
    return SampleSelection(group, tuple(selected), None, None, tuple(sorted(excluded.items())))


def decision(n: int, days: int, cov: Coverage, g1: PairedDifference | None, g2: PairedDifference | None) -> str:
    if n < MIN_CASES or days < MIN_DAYS:
        return "accruing"
    for difference in (g1, g2):
        if (difference is None or difference.n != n or difference.standard_error is None
                or not isfinite(difference.mean) or not isfinite(difference.standard_error)
                or difference.standard_error < 0):
            raise ValueError("The locked verdict requires finite paired differences on the full sample")
    return "pass" if (cov.passes and g1.mean + STANDARD_ERRORS * g1.standard_error <= MARGIN
                       and g2.mean + STANDARD_ERRORS * g2.standard_error <= MARGIN) else "keep incumbent"


@dataclass(frozen=True)
class ScoreReport:
    group: str
    cases: int
    days: int
    cutoff: date
    eligible_attempts: int
    candidate_available: int
    verdict: str
    g1: PairedDifference
    g2: PairedDifference
    components: tuple[tuple[str, ComponentScore], ...]
    calibration: tuple[tuple[str, tuple[CalibrationBin, ...]], ...]
    surfaces: tuple[tuple[str, int], ...]
    candidate_gated: int
    incumbent_gated: int


def score_sample(selection: SampleSelection, cov: Coverage) -> ScoreReport:
    cases = selection.cases
    days = len({utc_day(c.kickoff) for c in cases})
    if selection.cutoff is None or len(cases) < MIN_CASES or days < MIN_DAYS:
        raise ValueError("No losses may be computed before locking a mature sample")
    if not {c.match_id for c in cases} <= set(cov.available_ids) <= set(cov.eligible_ids):
        raise ValueError("The locked sample requires its complete coverage ledger")
    outcomes = [c.p1_won for c in cases]
    values = {name: [getattr(c.probabilities, name) for c in cases]
              for name in ("candidate", "incumbent", "market", "candidate_elo", "incumbent_elo")}
    g1 = paired_loss_difference(values["candidate"], values["incumbent"], outcomes)
    g2 = paired_loss_difference(values["candidate"], values["market"], outcomes)
    return ScoreReport(
        selection.group, len(cases), days, selection.cutoff, len(cov.eligible_ids), len(cov.available_ids),
        decision(len(cases), days, cov, g1, g2), g1, g2,
        tuple((name, score_component(probabilities, outcomes)) for name, probabilities in values.items()),
        tuple((name, tuple(calibration_bins(values[name], outcomes))) for name in ("candidate", "incumbent", "market")),
        tuple(sorted(Counter(c.surface or "Unknown" for c in cases).items())),
        sum(c.candidate_gated for c in cases), sum(c.incumbent_gated for c in cases),
    )
